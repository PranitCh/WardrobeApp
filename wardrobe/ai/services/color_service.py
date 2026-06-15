from ..models.color_extractor import ColorExtractor

extractor = ColorExtractor()

class ColorService:
    @staticmethod
    def extract(image_path: str):
        hist = extractor.extract_color_histogram(image_path)
        colors, percentages = extractor.get_dominant_colors(image_path, n_colors=3)
        color_names = [extractor.get_color_category(*c) for c in colors]

        return {
            "histogram": hist,
            "colors_rgb": colors,
            "percentages": percentages,
            "color_names": color_names,
            "primary_color": color_names[0]
        }