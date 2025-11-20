import os
import requests
import zipfile
import io
import yaml
import shutil
import gzip
import qrcode
from jinja2 import Environment, FileSystemLoader
from htmlmin import minify
from PIL import Image

# --- Configuration ---
PICO_URL = "https://github.com/picocss/pico/archive/refs/heads/main.zip"
OUTPUT_DIR = "out"
ASSETS_SRC_DIR = "assets"
CSS_DIR = os.path.join(OUTPUT_DIR, "css")

# --- 1. Setup Environment ---
print("🧹 Cleaning up old build and setting up environment...")
if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
os.makedirs(CSS_DIR, exist_ok=True)
print(f"'{OUTPUT_DIR}/' directory is ready.")

shutil.copy2("LICENSE", OUTPUT_DIR) if os.path.exists("LICENSE") else None

# --- 2. Fetch and Extract PicoCSS ---
print(f"🚚 Fetching PicoCSS...")
try:
    response = requests.get(PICO_URL)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        pico_css_path = "pico-main/css/pico.min.css"
        z.extract(pico_css_path, path=OUTPUT_DIR)
        final_css_path = os.path.join(CSS_DIR, "pico.min.css")
        shutil.move(os.path.join(OUTPUT_DIR, pico_css_path), final_css_path)
        shutil.rmtree(os.path.join(OUTPUT_DIR, "pico-main"))
    print("✅ PicoCSS downloaded.")
    print("📦 Gzipping CSS...")
    with open(final_css_path, 'rb') as f_in:
        with gzip.open(final_css_path + '.gz', 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    print("✅ CSS has been gzipped.")
except requests.exceptions.RequestException as e:
    print(f"❌ Error fetching PicoCSS: {e}")
    exit(1)

# --- 3. Process and Optimize Assets ---
print("🖼️  Processing and optimizing assets...")
assets_dest_dir = os.path.join(OUTPUT_DIR, ASSETS_SRC_DIR)
if not os.path.exists(ASSETS_SRC_DIR):
    print(f"⚠️  Warning: Source assets directory '{ASSETS_SRC_DIR}' not found. Skipping.")
else:
    shutil.copytree(ASSETS_SRC_DIR, assets_dest_dir, dirs_exist_ok=True)
    for root, _, files in os.walk(assets_dest_dir):
        for file in files:
            # ... (asset processing logic remains the same)
            file_path = os.path.join(root, file)
            file_name, file_ext = os.path.splitext(file_path)
            if file_ext.lower() in ['.jpg', '.jpeg', '.png']:
                try:
                    with Image.open(file_path) as img:
                        webp_path = f"{file_name}.webp"
                        img.save(webp_path, 'webp', lossless=True)
                    os.remove(file_path)
                    print(f"  - Converted {file} to WebP.")
                except Exception as e:
                    print(f"  - ❌ Error converting {file}: {e}")
            else:
                print(f"  - Copied {file} directly.")
    print("✅ Assets processed.")

# --- 4. Load Data and Generate QR Code ---
print("📝 Loading data from details.yaml...")
try:
    with open("details.yaml", "r", encoding="utf-8") as f:
        details = yaml.safe_load(f)
    if not details:
        print("❌ Error: 'details.yaml' is empty or invalid.")
        exit(1)

    # --- 4a. NEW: Generate QR Code ---
    if 'qr_code' in details and 'url' in details['qr_code']:
        print("🔳 Generating QR Code...")
        qr_url = details['qr_code']['url']
        qr_img = qrcode.make(qr_url, border=2)
        
        # Define path inside the output assets directory
        qr_filename = "qr_code_generated.webp"
        qr_output_path = os.path.join(assets_dest_dir, qr_filename)
        
        # Ensure the destination directory exists
        os.makedirs(assets_dest_dir, exist_ok=True)
        
        # Save as lossless WebP
        qr_img.save(qr_output_path, 'webp', lossless=True)
        
        # Inject the generated path back into the details dict for the template
        details['images']['qr'] = os.path.join(ASSETS_SRC_DIR, qr_filename).replace("\\", "/")
        print(f"✅ QR Code for '{qr_url}' generated.")
    else:
        print("⚠️  Warning: 'qr_code.url' not found in details.yaml. Skipping QR generation.")

    env = Environment(loader=FileSystemLoader("."))
    template = env.get_template("template.html")
except FileNotFoundError as e:
    print(f"❌ Error: {e}")
    exit(1)

# --- 5. Render and Minify HTML ---
print("✨ Rendering and minifying the final HTML...")
rendered_html = template.render(details)
minified_html = minify(rendered_html, remove_empty_space=True, remove_comments=True)

# --- 6. Write Final Output ---
output_path = os.path.join(OUTPUT_DIR, "index.html")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(minified_html)


print(f"\n🚀 Success! Your ridiculously fast website has been built in the '{OUTPUT_DIR}/' folder. 🚀")
