from wardrobe.ai.models.color_extractor import ColorExtractor

extractor = ColorExtractor()


def extract_colors(image_path: str):
    hist = extractor.extract_color_histogram(image_path)

    colors, percentages = extractor.get_dominant_colors(
        image_path,
        n_colors=3
    )

    color_names = [
        extractor.get_color_category(*color)
        for color in colors
    ]

    return {
        "colors_rgb": [
            [int(x) for x in color]
            for color in colors
        ],
        "percentages": [
            float(x)
            for x in percentages
        ],
        "color_names": color_names,
        "primary_color": color_names[0]
    }