# File: snap_text.py
import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os
from .utils import hex_to_rgb  

class SnapTextOverlay:
    """
    Applies a basic Snap-style text overlay with a semi-transparent bar.
    Supports text wrapping and various placement options.
    """

    @staticmethod
    def wrap_text_pixel_width(draw, text, font, max_width):
        lines = [];
        if not text or max_width <= 0 or not hasattr(font, 'size'): return lines
        paragraphs = text.split('\n'); all_lines = []
        for paragraph in paragraphs:
            if not paragraph.strip(): all_lines.append(""); continue
            words = paragraph.split(' '); current_line = ""
            for word in words:
                word = word.strip();
                if not word: continue
                test_line = current_line + (" " if current_line else "") + word; line_width = 0
                try: bbox = draw.textbbox((0, 0), test_line, font=font, anchor="lt"); line_width = bbox[2] - bbox[0]
                except Exception as e: line_width = len(test_line) * font.size * 0.6
                if line_width <= max_width: current_line = test_line
                else:
                    if current_line: all_lines.append(current_line)
                    try: word_bbox = draw.textbbox((0,0), word, font=font, anchor='lt'); current_word_width = word_bbox[2]-word_bbox[0]
                    except: current_word_width = len(word) * font.size * 0.6
                    if current_word_width > max_width:
                        temp_word = "";
                        for i, char in enumerate(word):
                             try: char_bbox = draw.textbbox((0,0), temp_word + char, font=font, anchor='lt'); current_width = char_bbox[2]-char_bbox[0]
                             except: current_width = len(temp_word + char) * font.size * 0.6
                             if current_width > max_width and temp_word: all_lines.append(temp_word); temp_word = char
                             else: temp_word += char
                        current_line = temp_word
                    else: current_line = word
            if current_line: all_lines.append(current_line)
        return all_lines

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "text": ("STRING", {"default": "Your Text Here", "multiline": False}),
                "font_name": ("STRING", {"default": "arial.ttf"}),
                "font_size_ratio": ("FLOAT", {"default": 0.05, "min": 0.01, "max": 0.2, "step": 0.005}),
                "vertical_placement": (["top", "middle", "bottom", "custom"], {"default": "middle"}),
                "custom_vertical_percentage": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "text_color": ("STRING", {"default": "#FFFFFF", "multiline": False}),
                "vertical_padding_ratio_of_size": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 3.0, "step": 0.05}),
                "line_spacing": ("INT", {"default": 4, "min": 0, "max": 50, "step": 1}),
                "bar_color": ("STRING", {"default": "#000000", "multiline": False}),
                "bar_alpha": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"
    CATEGORY = "ComfySnap"

    def execute(self, image: torch.Tensor, text: str, font_name: str,
                font_size_ratio: float, vertical_padding_ratio_of_size: float,
                line_spacing: int, vertical_placement: str,
                custom_vertical_percentage: float, text_color: str, bar_color: str,
                bar_alpha: float):

        # Add input validation for image shape
        if len(image.shape) != 4:
            raise ValueError("Input image must be a 4D tensor with shape (batch_size, height, width, channels).")

        # Improved font handling
        font_to_use = None
        target_font_size = max(1, int(image.shape[2] * font_size_ratio))
        
        # Windows font locations
        system_fonts = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'Fonts')
        
        # Try different font paths based on OS
        font_paths = [
            font_name,  # First try the exact path provided
            os.path.join(system_fonts, font_name),  # Windows system fonts directory
            os.path.join(os.getcwd(), font_name),  # Current working directory
            os.path.join(os.path.dirname(os.path.abspath(__file__)), font_name),  # Same directory as this script
            # Windows fonts
            os.path.join(system_fonts, 'arial.ttf'),
            os.path.join(system_fonts, 'calibri.ttf'),
            os.path.join(system_fonts, 'segoeui.ttf'),
            # Add any additional fonts or paths here
        ]
        
        # Try each font path
        for path in font_paths:
            if os.path.exists(path):
                try:
                    font_to_use = ImageFont.truetype(path, target_font_size)
                    print(f"Using font: {path}")
                    break
                except Exception as e:
                    print(f"Failed to load font {path}: {e}")
        
        # If no font was loaded, use PIL's default font
        if font_to_use is None:
            try:
                print("Using PIL's default font")
                font_to_use = ImageFont.load_default()
            except Exception as e:
                print(f"Error loading default font: {e}")
                # Continue without a font, text may not render correctly

        text = str(text); batch_size, img_height, img_width, channels = image.shape
        output_images = [];

        bar_rgb = hex_to_rgb(bar_color); text_rgb = hex_to_rgb(text_color)
        alpha_int = int(bar_alpha * 255); bar_rgba = bar_rgb + (alpha_int,)

        for i in range(batch_size):
            img_pil_rgb = Image.fromarray((image[i].cpu().numpy() * 255).astype(np.uint8)).convert('RGB')
            base_img_rgba = img_pil_rgb.convert("RGBA"); temp_draw = ImageDraw.Draw(Image.new("RGB", (1,1)))
            target_font_size = max(1, int(img_width * font_size_ratio)); font_load_error=False

            if font_to_use is None:
                 output_images.append(image[i])
                 continue

            text_height = 0; bar_height = 5; lines = []; padding_x = 0
            if font_to_use and text:
                padding_x = int(img_width * 0.025); max_text_width_pixels = img_width - (2 * padding_x)
                lines = self.wrap_text_pixel_width(temp_draw, text, font_to_use, max_text_width_pixels)
                if len(lines) <= 1:
                    text_to_draw = lines[0] if lines else ""
                    if text_to_draw:
                        try: bbox = temp_draw.textbbox((0,0), text_to_draw, font=font_to_use, anchor='lt'); text_height = bbox[3] - bbox[1]
                        except Exception as e: print(f"Error measuring single line: {e}"); text_height = target_font_size
                    else: text_height = 0
                else:
                    wrapped_text = '\n'.join(lines)
                    try: final_bbox = temp_draw.multiline_textbbox((0, 0), wrapped_text, font=font_to_use, spacing=line_spacing, anchor="lt"); text_height = final_bbox[3] - final_bbox[1]
                    except Exception as e: text_height = max(1, len(lines)) * target_font_size + max(0, len(lines) - 1) * line_spacing
                abs_padding_pixels = int(target_font_size * vertical_padding_ratio_of_size); bar_height = max(5, text_height + abs_padding_pixels); bar_height = min(bar_height, img_height)

            y_position = 0
            if bar_height >= img_height: y_position = 0
            elif vertical_placement == "top": y_position = 0
            elif vertical_placement == "middle": y_position = (img_height - bar_height) // 2
            elif vertical_placement == "bottom": y_position = img_height - bar_height
            elif vertical_placement == "custom":
                 percentage_factor = 1.0 - (custom_vertical_percentage / 100.0); y_position = int((img_height - bar_height) * percentage_factor); y_position = max(0, min(y_position, img_height - bar_height))
            else: y_position = (img_height - bar_height) // 2

            txt_layer = Image.new("RGBA", base_img_rgba.size, (255, 255, 255, 0)); draw_layer = ImageDraw.Draw(txt_layer)
            if font_to_use and text:
                if bar_alpha > 0: draw_layer.rectangle([(0, y_position), (img_width, y_position + bar_height)], fill=bar_rgba)
                center_x = img_width // 2; center_y = y_position + bar_height // 2
                try:
                    if len(lines) <= 1:
                        text_to_draw = lines[0] if lines else "";
                        if text_to_draw: draw_layer.text((center_x, center_y), text_to_draw, fill=text_rgb, font=font_to_use, anchor="mm")
                    else:
                        wrapped_text = '\n'.join(lines); draw_layer.multiline_text((center_x, center_y), wrapped_text, fill=text_rgb, font=font_to_use, spacing=line_spacing, anchor="mm", align="center")
                except Exception as e: print(f"Error drawing text: {e}")

            combined_img_rgba = Image.alpha_composite(base_img_rgba, txt_layer); final_pil_rgb = combined_img_rgba.convert("RGB")
            output_img_np = np.array(final_pil_rgb).astype(np.float32) / 255.0; output_images.append(torch.from_numpy(output_img_np))

        if not output_images: return (image,)
        output_tensor = torch.stack(output_images)
        return (output_tensor,)

NODE_CLASS_MAPPINGS = { "SnapTextOverlay": SnapTextOverlay }
NODE_DISPLAY_NAME_MAPPINGS = { "SnapTextOverlay": "Snap Text" }