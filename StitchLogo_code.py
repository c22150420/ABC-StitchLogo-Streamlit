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
# 3) Process a single image
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
# 4) Streamlit App
# ——————————————————————————————
TEMPLATE_PATH = 'logo_template.jpeg'  # Place your logo template in the app folder

# Fixed parameters
BASE_RATIO   = 0.1
EXPONENT     = 0.8
LEFT_FRAC    = 0.37
CENTER_FRAC  = 0.38
RIGHT_FRAC   = 1.0 - LEFT_FRAC - CENTER_FRAC
SLICE_RATIOS = (LEFT_FRAC, CENTER_FRAC, RIGHT_FRAC)

st.title("📸 Photo + Logo Template Stitcher")

st.write(
    "You can upload individual photos or a ZIP file containing photos. "
    "Total upload size must not exceed 200 MB."
)

uploads = st.file_uploader(
    "Upload photos or ZIP (jpg, jpeg, png, zip)",
    type=["jpg", "jpeg", "png", "zip"],
    accept_multiple_files=True
)

if st.button("Process All"):
    if not uploads:
        st.error("Please upload at least one photo or a ZIP file.")
    else:
        total_size = sum(f.size for f in uploads)
        if total_size > 200 * 1024 * 1024:
            st.error("Total upload size exceeds 200 MB. Please reduce the upload.")
        else:
            try:
                template = Image.open(TEMPLATE_PATH).convert("RGB")
            except Exception:
                st.error(f"Cannot load template from '{TEMPLATE_PATH}'.")
            else:
                zip_buf = BytesIO()
                with zipfile.ZipFile(zip_buf, mode="w") as zf:
                    for file in uploads:
                        name = file.name.lower()
                        if name.endswith(".zip"):
                            with zipfile.ZipFile(BytesIO(file.read())) as in_zip:
                                for info in in_zip.infolist():
                                    if info.filename.lower().endswith((".jpg", ".jpeg", ".png")):
                                        with in_zip.open(info) as img_f:
                                            photo = Image.open(img_f).convert("RGB")
                                            photo = correct_orientation(photo)
                                            stitched = process_image(
                                                photo, template,
                                                BASE_RATIO, EXPONENT, SLICE_RATIOS
                                            )
                                            out_buf = BytesIO()
                                            stitched.save(out_buf, format="JPEG")
                                            zf.writestr(f"stitched_{info.filename}", out_buf.getvalue())
                                            out_buf.close()
                        else:
                            photo = Image.open(file).convert("RGB")
                            photo = correct_orientation(photo)
                            stitched = process_image(
                                photo, template,
                                BASE_RATIO, EXPONENT, SLICE_RATIOS
                            )
                            out_buf = BytesIO()
                            stitched.save(out_buf, format="JPEG")
                            zf.writestr(f"stitched_{file.name}", out_buf.getvalue())
                            out_buf.close()
                zip_buf.seek(0)
                st.download_button(
                    "Download All as ZIP",
                    data=zip_buf,
                    file_name="stitched_images.zip",
                    mime="application/zip"
                )
