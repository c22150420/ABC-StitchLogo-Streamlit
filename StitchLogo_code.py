import streamlit as st
from PIL import Image, ExifTags
import zipfile
from io import BytesIO

# ——————————————————————————————
# 1) Fix image orientation via EXIF
# ——————————————————————————————
def correct_orientation(img: Image.Image) -> Image.Image:
    try:
        for tag, name in ExifTags.TAGS.items():
            if name == 'Orientation':
                orientation_tag = tag
                break
        exif = img._getexif()
        if exif is not None:
            orient = exif.get(orientation_tag)
            if orient == 3:
                img = img.rotate(180, expand=True)
            elif orient == 6:
                img = img.rotate(270, expand=True)
            elif orient == 8:
                img = img.rotate(90, expand=True)
    except Exception:
        pass
    return img

# ——————————————————————————————
# 2) Dynamic template slicer + stretcher
# ——————————————————————————————
def build_adaptive_template(
    template: Image.Image,
    target_width: int,
    target_height: int,
    slice_ratios=(0.37, 0.38, 0.25),
) -> Image.Image:
    orig_w, orig_h = template.size
    scale = target_height / orig_h
    scaled_w = int(orig_w * scale)
    scaled = template.resize((scaled_w, target_height), Image.LANCZOS)

    left_ratio, center_ratio, right_ratio = slice_ratios
    left_w = int(scaled_w * left_ratio)
    right_w = int(scaled_w * right_ratio)
    center_w = scaled_w - left_w - right_w

    left = scaled.crop((0, 0, left_w, target_height))
    center = scaled.crop((left_w, 0, left_w + center_w, target_height))
    right = scaled.crop((left_w + center_w, 0, scaled_w, target_height))

    if left_w + right_w > target_width:
        tmp = Image.new("RGB", (left_w + right_w, target_height))
        tmp.paste(left, (0, 0))
        tmp.paste(right, (left_w, 0))
        new_h = int(target_height * (target_width / (left_w + right_w)))
        return tmp.resize((target_width, new_h), Image.LANCZOS)
    else:
        needed = target_width - left_w - right_w
        center_stretched = center.resize((needed, target_height), Image.LANCZOS)
        out = Image.new("RGB", (target_width, target_height))
        out.paste(left, (0, 0))
        out.paste(center_stretched, (left_w, 0))
        out.paste(right, (left_w + needed, 0))
        return out

# ——————————————————————————————
# 3) Process single image: stitch photo + template
# ——————————————————————————————
def process_image(
    photo: Image.Image,
    template: Image.Image,
    base_ratio: float,
    exponent: float,
    slice_ratios,
) -> Image.Image:
    w, h = photo.size
    aspect = w / h
    h1 = int(w * base_ratio * (aspect ** (-exponent)))
    adapt = build_adaptive_template(
        template,
        target_width=w,
        target_height=h1,
        slice_ratios=slice_ratios,
    )
    out_h = h + adapt.height
    out = Image.new("RGB", (w, out_h), (255, 255, 255))
    out.paste(photo, (0, 0))
    out.paste(adapt, (0, h))
    return out

# ——————————————————————————————
# 4) Streamlit UI
# ——————————————————————————————
# Template image path: place your logo template in the app folder with this name
TEMPLATE_PATH = 'logo_template.jpeg'

# Fixed ratios (no user adjustment)
BASE_RATIO     = 0.1
LEFT_FRAC      = 0.37
CENTER_FRAC    = 0.38
RIGHT_FRAC     = 1.0 - LEFT_FRAC - CENTER_FRAC
SLICE_RATIOS   = (LEFT_FRAC, CENTER_FRAC, RIGHT_FRAC)

st.title("📸 Photo + Logo Template Stitcher")

# User can only adjust height exponent; explain its effect
st.write(
    "**Height Exponent:** Determines template bar thickness based on photo shape. "
    "Higher values → thicker bar for tall images; lower values → thinner bar."
)
exponent = st.sidebar.slider(
    "Height Exponent", min_value=0.1, max_value=2.0, value=0.8, step=0.1
)

photos = st.file_uploader(
    "Upload Photos", type=["jpg", "jpeg", "png"], accept_multiple_files=True
)

if st.button("Process All"):  # unified zip generation
    if photos:
        try:
            template = Image.open(TEMPLATE_PATH).convert("RGB")
        except Exception:
            st.error(f"Cannot load template from '{TEMPLATE_PATH}'.")
        else:
            zip_buf = BytesIO()
            with zipfile.ZipFile(zip_buf, mode="w") as zf:
                for photo_file in photos:
                    photo = Image.open(photo_file).convert("RGB")
                    photo = correct_orientation(photo)
                    stitched = process_image(
                        photo, template, BASE_RATIO, exponent, SLICE_RATIOS
                    )
                    img_buf = BytesIO()
                    stitched.save(img_buf, format="JPEG")
                    zf.writestr(f"stitched_{photo_file.name}", img_buf.getvalue())
                    img_buf.close()
            zip_buf.seek(0)
            st.download_button(
                "Download All as ZIP", data=zip_buf,
                file_name="stitched_images.zip",
                mime="application/zip"
            )
    else:
        st.error("Please upload at least one photo.")
