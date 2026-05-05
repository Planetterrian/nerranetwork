#!/usr/bin/env python3
"""
Create optimized logo images for Apple Podcast RSS feed.
Apple requires: 1400x1400px minimum, square, JPG or PNG
"""

from PIL import Image, ImageDraw
import sys
from pathlib import Path

def create_rss_image(input_path: Path, output_path: Path, size: int = 1400):
    """
    Create a square RSS-optimized image from the logo.
    Centers the logo on a square background using brand colors.
    """
    # Brand colors from guidelines
    brand_colors = {
        'deep_teal': '#017A99',      # Deep teal-blue
        'light_teal': '#35B5C4',     # Lighter turquoise-blue
        'yellow': '#F2D20D'          # Bright yellow
    }
    
    # Open the original logo
    try:
        logo = Image.open(input_path)
        logo = logo.convert('RGBA')
    except Exception as e:
        print(f"Error opening logo: {e}")
        return False
    
    # Create a square canvas with white background (or light teal for brand consistency)
    canvas = Image.new('RGB', (size, size), color='#FFFFFF')
    
    # Calculate scaling to fit logo in square with padding
    padding = int(size * 0.1)  # 10% padding
    max_logo_size = size - (padding * 2)
    
    # Calculate aspect ratio
    logo_aspect = logo.width / logo.height
    canvas_aspect = 1.0  # Square
    
    if logo_aspect > canvas_aspect:
        # Logo is wider - fit to width
        new_width = max_logo_size
        new_height = int(new_width / logo_aspect)
    else:
        # Logo is taller - fit to height
        new_height = max_logo_size
        new_width = int(new_height * logo_aspect)
    
    # Resize logo maintaining aspect ratio
    logo_resized = logo.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Center the logo on canvas
    x_offset = (size - new_width) // 2
    y_offset = (size - new_height) // 2
    
    # Paste logo onto canvas (handling transparency)
    if logo_resized.mode == 'RGBA':
        canvas.paste(logo_resized, (x_offset, y_offset), logo_resized)
    else:
        canvas.paste(logo_resized, (x_offset, y_offset))
    
    # Save as JPG (Apple accepts both JPG and PNG, but JPG is smaller)
    try:
        canvas.save(output_path, 'JPEG', quality=95, optimize=True)
        print(f"✓ Created RSS image: {output_path} ({size}x{size}px)")
        return True
    except Exception as e:
        print(f"Error saving image: {e}")
        return False

def main():
    project_root = Path(__file__).parent
    input_logo = project_root / "PlanetTerrian logo only final.jpg"
    output_rss = project_root / "planetterrian-podcast-image.jpg"
    
    if not input_logo.exists():
        print(f"Error: Logo file not found: {input_logo}")
        sys.exit(1)
    
    print(f"Processing logo: {input_logo}")
    print(f"Creating RSS-optimized image: {output_rss}")
    
    success = create_rss_image(input_logo, output_rss, size=1400)
    
    if success:
        print(f"\n✓ Successfully created RSS image at: {output_rss}")
        print("  This image meets Apple Podcast requirements:")
        print("  - 1400x1400px (minimum requirement)")
        print("  - Square aspect ratio")
        print("  - JPEG format")
    else:
        print("\n✗ Failed to create RSS image")
        sys.exit(1)

if __name__ == "__main__":
    main()

