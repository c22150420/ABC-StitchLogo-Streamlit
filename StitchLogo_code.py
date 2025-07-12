import streamlit as st
from PIL import Image, ExifTags
from io import BytesIO

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


def build_adaptive_template(template: Image.Image, target_width: int, target_height: int, slice_ratios=(0.45, 0.30, 0.25)) -> Image.Image:
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


def process_image(photo: Image.Image, template: Image.Image, base_ratio: float, exponent: float, slice_ratios) -> Image.Image:
    w, h = photo.size
    aspect = w / h
    h1 = int(w * base_ratio * (aspect ** (-exponent)))
    adapt = build_adaptive_template(template, target_width=w, target_height=h1, slice_ratios=slice_ratios)
    out_h = h + adapt.height
    out = Image.new("RGB", (w, out_h), (255, 255, 255))
    out.paste(photo, (0, 0))
    out.paste(adapt, (0, h))
    return out

# Streamlit UI
st.title("📸 Photo + Template Stitcher")

st.sidebar.header("Settings")
template_file = st.sidebar.file_uploader("Upload Template Image", type=["jpg", "jpeg", "png"])
photos = st.sidebar.file_uploader("Upload Photos", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
base_ratio = st.sidebar.slider("Base Ratio", min_value=0.05, max_value=0.5, value=0.10, step=0.01)
exponent = st.sidebar.slider("Height Exponent", min_value=0.1, max_value=2.0, value=0.8, step=0.1)
left_frac = st.sidebar.slider("Left Slice Fraction", min_value=0.1, max_value=0.6, value=0.45, step=0.01)
center_frac = st.sidebar.slider("Center Slice Fraction", min_value=0.1, max_value=0.6, value=0.30, step=0.01)
# ensure sum <=1
right_frac = 1.0 - left_frac - center_frac
slice_ratios = (left_frac, center_frac, right_frac)

if st.sidebar.button("Process All"):
    if template_file and photos:
        template = Image.open(template_file).convert("RGB")
        for photo_file in photos:
            photo = Image.open(photo_file).convert("RGB")
            photo = correct_orientation(photo)
            stitched = process_image(photo, template, base_ratio, exponent, slice_ratios)
            st.image(stitched, caption=f"Stitched: {photo_file.name}", use_column_width=True)
            buf = BytesIO()
            stitched.save(buf, format="JPEG")
            st.download_button(
                label="Download",
                data=buf.getvalue(),
                file_name=f"stitched_{photo_file.name}",
                mime="image/jpeg"
            )
    else:
        st.error("Please upload both a template and at least one photo.")
