import os
import json
from tkinter import Tk, Label, Button, Entry, Checkbutton, IntVar, filedialog, StringVar, ttk, Scale
import fitz  # PyMuPDF for PDF/image manipulation
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

CONFIG_FILE = "config.txt"

def add_background_to_pdf(pdf, background_image_path, opacity=1.0, bg_x=0, bg_y=0, scale_factor=1.0):
    if not os.path.exists(background_image_path):
        print("Background image not found, skipping background step.")
        return

    for page in pdf:
        page_width = page.rect.width
        page_height = page.rect.height

        bg_image = Image.open(background_image_path).convert("RGBA")
        bg_width, bg_height = bg_image.size
        aspect_ratio = bg_width / bg_height

        new_bg_width = int(page_width * scale_factor)
        new_bg_height = int(new_bg_width / aspect_ratio)

        bg_image = bg_image.resize((new_bg_width, new_bg_height), Image.LANCZOS)

        alpha = bg_image.split()[3]
        alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
        bg_image.putalpha(alpha)

        temp_bg_img_path = "temp_background.png"
        bg_image.save(temp_bg_img_path)

        x_position = (page_width - new_bg_width) / 2 + bg_x
        y_position = (page_height - new_bg_height) / 2 + bg_y

        img_rect = fitz.Rect(x_position, y_position, x_position + new_bg_width, y_position + new_bg_height)
        page.insert_image(img_rect, filename=temp_bg_img_path, overlay=True)

        os.remove(temp_bg_img_path)

def add_text_as_watermark(pdf, text, x, y, opacity=1.0, font_path="arial.ttf", font_size=None, watermark_url=None):
    for page in pdf:
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height

        if font_size is None:
            dynamic_font_size = int(page_width / 30)
        else:
            dynamic_font_size = font_size

        try:
            font = ImageFont.truetype(font_path, dynamic_font_size)
        except Exception as e:
            print(f"Failed to load font '{font_path}': {e}. Using default font.")
            font = ImageFont.load_default()

        draw = ImageDraw.Draw(Image.new("RGBA", (500, 100), (255, 255, 255, 0)))
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1] + 10

        text_img = Image.new("RGBA", (text_width, text_height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(text_img)
        draw.text((0, 0), text, fill=(0, 0, 0, int(255 * opacity)), font=font)

        temp_text_img_path = "temp_text_watermark.png"
        text_img.save(temp_text_img_path)

        # Centered position if not provided
        x = (page_width / 2) - (text_width / 2) if x is None else x
        y = page_height - text_height - 15 if y is None else y

        text_rect = fitz.Rect(x, y, x + text_width, y + text_height)

        page.insert_image(
            text_rect,
            filename=temp_text_img_path,
            overlay=True
        )

        # Add hyperlink only to the text watermark
        if watermark_url:
            page.insert_link({
                "kind": fitz.LINK_URI,
                "from": text_rect,
                "uri": watermark_url
            })

    os.remove(temp_text_img_path)

def process_single_pdf(
    source_pdf_path, destination_pdf_path, other_pdf_path, text, image_path, image_x, image_y, image_opacity,
    text_x, text_y, text_opacity, background_image_path, background_opacity, bg_x, bg_y,
    add_bg, add_text, scale_factor, watermark_url, append_pdf_path=None
):
    source_pdf = fitz.open(source_pdf_path)
    temp_watermarked_pdf = "temp_watermarked.pdf"

    if add_bg and background_image_path:
        add_background_to_pdf(source_pdf, background_image_path, background_opacity, bg_x, bg_y, scale_factor)

    if add_text:
        add_text_as_watermark(source_pdf, text, None, None, text_opacity, font_path="arial.ttf", font_size=font_size_var.get(), watermark_url=watermark_url)

    source_pdf.save(temp_watermarked_pdf)
    source_pdf.close()

    output_pdf = fitz.open()
    temp_watermarked_reader = fitz.open(temp_watermarked_pdf)
    other_pdf = fitz.open(other_pdf_path)

    target_width = temp_watermarked_reader[0].rect.width
    target_height = temp_watermarked_reader[0].rect.height

    for page in other_pdf:
        new_page = output_pdf.new_page(width=target_width, height=target_height)
        scale_x = target_width / page.rect.width
        scale_y = target_height / page.rect.height
        scale = min(scale_x, scale_y)
        mat = fitz.Matrix(scale, scale)
        new_page.show_pdf_page(new_page.rect, other_pdf, page.number, mat)

    output_pdf.insert_pdf(temp_watermarked_reader)
    output_pdf.save(destination_pdf_path, garbage=4, deflate=True)
    output_pdf.close()
    temp_watermarked_reader.close()

    # Append extra PDF if enabled and exists
    if append_pdf_path and os.path.exists(append_pdf_path):
    # Open the two PDFs but close them before saving combined file
        final_pdf = fitz.open(destination_pdf_path)
        append_pdf_file = fitz.open(append_pdf_path)
        
        combined_pdf = fitz.open()
        combined_pdf.insert_pdf(final_pdf)
        combined_pdf.insert_pdf(append_pdf_file)
        
        final_pdf.close()
        append_pdf_file.close()
        
        combined_pdf.save(destination_pdf_path, garbage=4, deflate=True)
        combined_pdf.close()
    if os.path.exists(temp_watermarked_pdf):
        os.remove(temp_watermarked_pdf)

    

def add_watermark_and_merge_pdfs(
    source_folder, other_pdf, destination_folder, image_path, text,
    image_x, image_y, image_opacity, text_x, text_y, text_opacity,
    background_image_path=None, background_opacity=1.0, bg_x=0, bg_y=0,
    add_bg=False, add_text=False, scale_factor=1.0, watermark_url=None,
    progress_callback=None, append_pdf_path=None
):
    os.makedirs(destination_folder, exist_ok=True)
    total_files = sum(len(files) for _, _, files in os.walk(source_folder) if any(f.endswith('.pdf') for f in files))
    completed_files = 0

    for root, _, files in os.walk(source_folder):
        relative_path = os.path.relpath(root, source_folder)
        dest_subfolder = os.path.join(destination_folder, relative_path)
        os.makedirs(dest_subfolder, exist_ok=True)

        for filename in files:
            if filename.endswith('.pdf'):
                source_pdf_path = os.path.join(root, filename)
                destination_pdf_path = os.path.join(dest_subfolder, filename)

                process_single_pdf(
                    source_pdf_path, destination_pdf_path, other_pdf, text, image_path, image_x, image_y, image_opacity,
                    text_x, text_y, text_opacity, background_image_path, background_opacity, bg_x, bg_y,
                    add_bg, add_text, scale_factor, watermark_url,
                    append_pdf_path=append_pdf_path
                )

                completed_files += 1
                if progress_callback:
                    progress_callback(completed_files / total_files * 100)

    completed_label.config(text="Completed!")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as file:
            return json.load(file)
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as file:
        json.dump(config, file)

def start_process():
    progress_bar["value"] = 0
    config = {
        "source_folder": source_folder.get(),
        "other_pdf": other_pdf.get(),
        "destination_folder": destination_folder.get(),
        "text": text.get(),
        "background_image": background_image.get(),
        "watermark_url": watermark_url.get(),
        "append_pdf_path": append_pdf_path.get()
    }
    save_config(config)
    completed_label.config(text="")
    add_watermark_and_merge_pdfs(
        config["source_folder"], config["other_pdf"], config["destination_folder"],
        image_path="", text=config["text"],
        image_x=220, image_y=-5, image_opacity=1.0, text_x=190, text_y=820,
        text_opacity=1.0, background_image_path=config["background_image"],
        background_opacity=background_trans.get(), bg_x=0, bg_y=0,
        add_bg=bg_var.get(), add_text=text_var.get(),
        scale_factor=background_scale.get(), watermark_url=config["watermark_url"],
        progress_callback=update_progress,
        append_pdf_path=append_pdf_path.get() if append_pdf_var.get() else None
    )

def update_progress(value):
    progress_bar["value"] = value
    root.update_idletasks()

# GUI Setup
root = Tk()
root.title("PDF Watermark and Merge Tool")
root.geometry("550x510")
root.configure(bg="#e1e1e1")
COMMON_PADY = 5
config = load_config()

Label(root, text="PDF Watermark and Merge Tool", font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=3, pady=(10, 20))

Label(root, text="Source Folder:").grid(row=1, column=0, sticky="e", pady=COMMON_PADY)
source_folder = StringVar(value=config.get("source_folder", ""))
Entry(root, textvariable=source_folder, width=40).grid(row=1, column=1)
Button(root, text="Browse", command=lambda: source_folder.set(filedialog.askdirectory())).grid(row=1, column=2)

Label(root, text="Front PDF Page:").grid(row=2, column=0, sticky="e", pady=COMMON_PADY)
other_pdf = StringVar(value=config.get("other_pdf", ""))
Entry(root, textvariable=other_pdf, width=40).grid(row=2, column=1)
Button(root, text="Browse", command=lambda: other_pdf.set(filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")]))).grid(row=2, column=2)

Label(root, text="Destination Folder:").grid(row=3, column=0, sticky="e", pady=COMMON_PADY)
destination_folder = StringVar(value=config.get("destination_folder", ""))
Entry(root, textvariable=destination_folder, width=40).grid(row=3, column=1)
Button(root, text="Browse", command=lambda: destination_folder.set(filedialog.askdirectory())).grid(row=3, column=2)

Label(root, text="Text Watermark:").grid(row=4, column=0, sticky="e", pady=COMMON_PADY)
text = StringVar(value=config.get("text", ""))
Entry(root, textvariable=text, width=40).grid(row=4, column=1, columnspan=2)

Label(root, text="Background Image:").grid(row=5, column=0, sticky="e", pady=COMMON_PADY)
background_image = StringVar(value=config.get("background_image", ""))
Entry(root, textvariable=background_image, width=40).grid(row=5, column=1)
Button(root, text="Browse", command=lambda: background_image.set(filedialog.askopenfilename(filetypes=[("Image files", "*.png;*.jpg;*.jpeg")]))).grid(row=5, column=2)

Label(root, text="Hypertext URL:").grid(row=6, column=0, sticky="e", pady=COMMON_PADY)
watermark_url = StringVar(value=config.get("watermark_url", ""))
Entry(root, textvariable=watermark_url, width=40).grid(row=6, column=1, columnspan=2)

bg_var = IntVar(value=1)
text_var = IntVar(value=1)
Checkbutton(root, text="Add Background Image", variable=bg_var).grid(row=7, column=1, sticky="w")
Checkbutton(root, text="Add Text Watermark", variable=text_var).grid(row=7, column=2, sticky="w")

Label(root, text="Font Size:").grid(row=8, column=0, sticky="e", pady=COMMON_PADY)
font_size_var = IntVar(value=25)
ttk.Spinbox(root, from_=0, to=150, textvariable=font_size_var, width=5).grid(row=8, column=1, sticky="w")

Label(root, text="Background Scale Factor:").grid(row=9, column=0, columnspan=2, sticky="w", pady=COMMON_PADY)
background_scale = Scale(root, from_=0.1, to=2.0, resolution=0.1, orient="horizontal", length=200)
background_scale.set(1.0)
background_scale.grid(row=9, column=1, columnspan=2)

Label(root, text="Background Transparency:").grid(row=10, column=0, columnspan=2, sticky="w", pady=COMMON_PADY)
background_trans = Scale(root, from_=0, to=1, resolution=0.01, orient="horizontal", length=200)
background_trans.set(0.13)
background_trans.grid(row=10, column=1, columnspan=2)

# New Append PDF option
append_pdf_var = IntVar(value=1)
append_pdf_path = StringVar(value=config.get("append_pdf_path", ""))

Checkbutton(root, text="Append Extra PDF at End", variable=append_pdf_var).grid(row=11, column=0, sticky="w")
Entry(root, textvariable=append_pdf_path, width=30).grid(row=11, column=1)
Button(root, text="Browse", command=lambda: append_pdf_path.set(filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")]))).grid(row=11, column=2)

progress_bar = ttk.Progressbar(root, orient="horizontal", length=300, mode="determinate")
progress_bar.grid(row=12, column=0, columnspan=3, pady=(COMMON_PADY, 0))

Button(root, text="Start Process", command=start_process).grid(row=13, column=0, columnspan=3, pady=COMMON_PADY)

completed_label = Label(root, text="", fg="green")
completed_label.grid(row=14, column=0, columnspan=3, pady=COMMON_PADY)

root.mainloop()
