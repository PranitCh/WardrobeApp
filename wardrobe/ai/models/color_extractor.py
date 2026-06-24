# color_extractor.py
import cv2
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from rembg import remove

class ColorExtractor:
    def __init__(self, hue_bins=18, saturation_bins=3, value_bins=3):
        """
        Initialize color extractor with HSV histogram parameters.
        Following the paper's approach of quantizing color space.
        
        Args:
            hue_bins: Number of bins for Hue (0-180 in OpenCV)
            saturation_bins: Number of bins for Saturation (0-255)
            value_bins: Number of bins for Value/Brightness (0-255)
        """
        self.hue_bins = hue_bins
        self.saturation_bins = saturation_bins
        self.value_bins = value_bins
        self.total_bins = hue_bins * saturation_bins * value_bins
    
    def remove_background(self, image_path, output_path=None):
        """
        Remove background from clothing image using AI-based segmentation.
        
        Args:
            image_path: Path to input image
            output_path: Optional path to save the masked image
            
        Returns:
            PIL Image with transparent background and numpy mask
        """
        # Load image
        input_img = Image.open(image_path)
        
        # Remove background using rembg (AI-based)
        output_img = remove(input_img)
        
        # Save if output path provided
        if output_path:
            output_img.save(output_path)
        
        # Convert to numpy array and extract mask
        img_array = np.array(output_img)
        
        # Create binary mask from alpha channel
        if img_array.shape[2] == 4:  # RGBA
            mask = img_array[:, :, 3] > 0  # Alpha channel
        else:
            mask = np.ones(img_array.shape[:2], dtype=bool)
        
        return output_img, mask
    
    def create_grabcut_mask(self, image_path):
        """
        Alternative method: Use GrabCut for semi-automatic segmentation.
        More interactive and works without external dependencies.
        
        Args:
            image_path: Path to input image
            
        Returns:
            Segmented image and mask
        """
        # Load image
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        # Create mask for GrabCut
        mask = np.zeros(img.shape[:2], np.uint8)
        
        # Define rectangle around the clothing item (80% of image)
        h, w = img.shape[:2]
        margin = 0.1
        rect = (int(w*margin), int(h*margin), 
                int(w*(1-margin)), int(h*(1-margin)))
        
        # Initialize background and foreground models
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)
        
        # Apply GrabCut
        cv2.grabCut(img, mask, rect, bgd_model, fgd_model, 
                    5, cv2.GC_INIT_WITH_RECT)
        
        # Create binary mask (0 and 2 are background, 1 and 3 are foreground)
        mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
        
        # Apply mask to image
        segmented = img * mask2[:, :, np.newaxis]
        
        return segmented, mask2
    
    def extract_color_histogram(self, image_path, use_mask=True, 
                                mask_method='rembg'):
        """
        Extract HSV color histogram from clothing image with background removal.
        
        Args:
            image_path: Path to clothing image
            use_mask: Whether to use background removal
            mask_method: 'rembg' or 'grabcut'
            
        Returns:
            Normalized histogram array
        """
        # Load image
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        # Get mask if requested
        mask = None
        if use_mask:
            if mask_method == 'rembg':
                _, mask = self.remove_background(image_path)
                mask = mask.astype(np.uint8) * 255
            elif mask_method == 'grabcut':
                _, mask = self.create_grabcut_mask(image_path)
                mask = mask * 255
        
        # Convert BGR to HSV
        hsv_img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Calculate 3D histogram with mask
        hist = cv2.calcHist(
            [hsv_img], 
            [0, 1, 2],  # H, S, V channels
            mask,  # Apply mask to focus on clothing only
            [self.hue_bins, self.saturation_bins, self.value_bins],
            [0, 180, 0, 256, 0, 256]  # HSV ranges in OpenCV
        )
        
        # Normalize histogram
        hist = cv2.normalize(hist, hist).flatten()
        
        return hist
    
    def merge_similar_colors(self, colors, percentages, distance_threshold=35):
        merged_colors = []
        merged_percentages = []

        for color, pct in zip(colors, percentages):
            color = np.array(color, dtype=np.float32)
            found = False

            for i, existing in enumerate(merged_colors):
                dist = np.linalg.norm(color - existing)
                if dist < distance_threshold:
                    total_pct = merged_percentages[i] + pct
                    merged_colors[i] = (
                        merged_colors[i] * merged_percentages[i] + color * pct
                    ) / total_pct
                    merged_percentages[i] = total_pct
                    found = True
                    break

            if not found:
                merged_colors.append(color)
                merged_percentages.append(float(pct))

        merged_colors = [np.uint8(np.round(c)) for c in merged_colors]

        return merged_colors, merged_percentages
    
    def get_dominant_colors(self, image_path, n_colors=5, use_mask=True,
                           mask_method='rembg'):
        """
        Extract dominant colors from clothing item only (background removed).
        
        Args:
            image_path: Path to clothing image
            n_colors: Number of dominant colors to extract
            use_mask: Whether to remove background
            mask_method: 'rembg' or 'grabcut'
            
        Returns:
            List of dominant colors in RGB format and their percentages
        """
        # Load image
        img = cv2.imread(image_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Get mask
        if use_mask:
            if mask_method == 'rembg':
                _, mask = self.remove_background(image_path)
            elif mask_method == 'grabcut':
                _, mask = self.create_grabcut_mask(image_path)
                mask = mask.astype(bool)
            
            # Apply mask to get only clothing pixels
            clothing_pixels = img[mask]
        else:
            # Use all pixels
            clothing_pixels = img.reshape(-1, 3)
        
        # Resize for faster processing
        if len(clothing_pixels) > 10000:
            indices = np.random.choice(len(clothing_pixels), 10000, replace=False)
            clothing_pixels = clothing_pixels[indices]
        
        pixels = np.float32(clothing_pixels)
        
        # K-means clustering
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
        _, labels, centers = cv2.kmeans(
            pixels, 
            n_colors, 
            None, 
            criteria, 
            10, 
            cv2.KMEANS_RANDOM_CENTERS
        )
        
        # Convert centers to uint8
        centers = np.uint8(centers)
        
        # Count pixels in each cluster
        counts = np.bincount(labels.flatten())
        
        # Sort by frequency
        sorted_indices = np.argsort(-counts)
        dominant_colors = centers[sorted_indices]
        color_percentages = counts[sorted_indices] / len(labels)

# 🔥 NEW: merge similar shades
        dominant_colors, color_percentages = self.merge_similar_colors(
            dominant_colors,
            color_percentages
        )

        return dominant_colors, color_percentages
    
    def visualize_segmentation(self, image_path, mask_method='rembg'):
        """
        Visualize the segmentation/background removal process.
        
        Args:
            image_path: Path to clothing image
            mask_method: 'rembg' or 'grabcut'
        """
        # Load original image
        original = cv2.imread(image_path)
        original = cv2.cvtColor(original, cv2.COLOR_BGR2RGB)
        
        # Get segmented version
        if mask_method == 'rembg':
            segmented_pil, mask = self.remove_background(image_path)
            segmented = np.array(segmented_pil)[:, :, :3]  # Remove alpha channel
        elif mask_method == 'grabcut':
            segmented, mask = self.create_grabcut_mask(image_path)
            segmented = cv2.cvtColor(segmented, cv2.COLOR_BGR2RGB)
        
        # Create visualization
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        
        axes[0].imshow(original)
        axes[0].set_title('Original Image')
        axes[0].axis('off')
        
        axes[1].imshow(mask, cmap='gray')
        axes[1].set_title('Segmentation Mask')
        axes[1].axis('off')
        
        axes[2].imshow(segmented)
        axes[2].set_title('Segmented Clothing')
        axes[2].axis('off')
        
        plt.tight_layout()
        plt.show()
    
    def visualize_colors(self, image_path, n_colors=5, use_mask=True,
                        mask_method='rembg'):
        """
        Visualize dominant colors from the clothing item only.
        """
        colors, percentages = self.get_dominant_colors(
            image_path, n_colors, use_mask, mask_method
        )
        
        # Create visualization
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 4))
        
        # Show original image
        img = Image.open(image_path)
        ax1.imshow(img)
        ax1.set_title('Original Image')
        ax1.axis('off')
        
        # Show segmented version
        if use_mask:
            if mask_method == 'rembg':
                seg_img, _ = self.remove_background(image_path)
            else:
                seg_img, _ = self.create_grabcut_mask(image_path)
                seg_img = cv2.cvtColor(seg_img, cv2.COLOR_BGR2RGB)
            ax2.imshow(seg_img)
            ax2.set_title('Segmented Clothing')
        else:
            ax2.imshow(img)
            ax2.set_title('No Segmentation')
        ax2.axis('off')
        
        # Show color palette
        palette = np.zeros((100, 500, 3), dtype=np.uint8)
        x_start = 0
        for i, (color, pct) in enumerate(zip(colors, percentages)):
            x_end = x_start + int(500 * pct)
            palette[:, x_start:x_end] = color
            x_start = x_end
        
        ax3.imshow(palette)
        ax3.set_title('Dominant Colors (Clothing Only)')
        ax3.axis('off')
        
        plt.tight_layout()
        plt.show()
        
        # Print color info
        print("\nDominant Colors from Clothing (RGB):")
        for i, (color, pct) in enumerate(zip(colors, percentages)):
            print(f"Color {i+1}: RGB{tuple(color)} - {pct*100:.1f}%")
    
    def rgb_to_hsv(self, r, g, b):
        """Convert RGB to HSV color space."""
        r, g, b = r/255.0, g/255.0, b/255.0
        max_c = max(r, g, b)
        min_c = min(r, g, b)
        diff = max_c - min_c
        
        # Hue calculation
        if diff == 0:
            h = 0
        elif max_c == r:
            h = (60 * ((g - b) / diff) + 360) % 360
        elif max_c == g:
            h = (60 * ((b - r) / diff) + 120) % 360
        else:
            h = (60 * ((r - g) / diff) + 240) % 360
        
        # Saturation calculation
        s = 0 if max_c == 0 else (diff / max_c) * 100
        
        # Value calculation
        v = max_c * 100
        
        return h, s, v
    
    def get_color_category(self, r, g, b):
        h, s, v = self.rgb_to_hsv(r, g, b)

        # ---------- very dark / neutral handling ----------
        if v < 12:
            return "Black"

        if s < 12:
            if v > 92:
                return "White"
            elif v > 72:
                return "Light Gray"
            elif v > 35:
                return "Gray"
            else:
                return "Charcoal"

        # ---------- warm muted tones ----------
        # beige / cream / brown family
        if 15 <= h < 50:
            if v > 82 and s < 28:
                return "Cream"
            elif v > 60 and s < 45:
                return "Beige"
            elif v < 38:
                return "Brown"
            else:
                return "Orange"

        # ---------- yellow / olive ----------
        if 50 <= h < 75:
            if v < 55:
                return "Olive"
            elif s < 35 and v > 75:
                return "Khaki"
            else:
                return "Yellow"

        # ---------- green ----------
        if 75 <= h < 155:
            if v < 45:
                return "Olive"
            return "Green"

        # ---------- cyan ----------
        if 155 <= h < 190:
            if v < 45:
                return "Teal"
            return "Cyan"

        # ---------- blue family ----------
        if 190 <= h < 255:
            if v < 28:
                return "Navy"
            elif v < 45:
                return "Dark Blue"
            elif v > 75 and s < 45:
                return "Sky Blue"
            else:
                return "Blue"

        # ---------- purple ----------
        if 255 <= h < 290:
            if v < 45:
                return "Plum"
            return "Purple"

        # ---------- pink / maroon ----------
        if 290 <= h < 345:
            if v < 45:
                return "Maroon"
            elif s < 35 and v > 70:
                return "Rose"
            else:
                return "Pink"

        # ---------- red ----------
        # h in [345, 360) or [0, 15)
        if v < 45:
            return "Maroon"
        return "Red"


# Example usage
if __name__ == "__main__":
    extractor = ColorExtractor()
    
    # Example image path
    image_path = "/Users/pranit/Documents/Code/Wardrobe App/AI/myward/bottom/WhatsApp Image 2026-04-06 at 00.05.36 (1).jpeg"
    
    try:
        print("=== Visualizing Segmentation ===")
        # Show segmentation results
        extractor.visualize_segmentation(image_path, mask_method='rembg')
        
        print("\n=== Extracting Colors (With Background Removal) ===")
        # Get histogram with background removed
        hist_masked = extractor.extract_color_histogram(
            image_path, 
            use_mask=True,
            mask_method='rembg'
        )
        print(f"Histogram shape: {hist_masked.shape}")
        
        # Get dominant colors from clothing only
        colors, percentages = extractor.get_dominant_colors(
            image_path,
            use_mask=True,
            mask_method='rembg'
        )
        
        print("\nDominant Colors (Clothing Only):")
        for i, (color, pct) in enumerate(zip(colors, percentages)):
            r, g, b = color
            category = extractor.get_color_category(r, g, b)
            print(f"{i+1}. {category}: RGB{tuple(color)} - {pct*100:.1f}%")
        
        # Visualize with comparison
        print("\n=== Visualizing Color Extraction ===")
        extractor.visualize_colors(image_path, use_mask=True, mask_method='rembg')
        
        print("\n=== Comparison: Without Background Removal ===")
        colors_no_mask, pct_no_mask = extractor.get_dominant_colors(
            image_path,
            use_mask=False
        )
        print("Dominant Colors (Entire Image):")
        for i, (color, pct) in enumerate(zip(colors_no_mask, pct_no_mask)):
            r, g, b = color
            category = extractor.get_color_category(r, g, b)
            print(f"{i+1}. {category}: RGB{tuple(color)} - {pct*100:.1f}%")
        
    except Exception as e:
        print(f"Error: {e}")
