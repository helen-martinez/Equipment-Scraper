import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import zipfile
import re
import json

# --------------------
# Site-specific scrapers
# --------------------

def Fastline(url_list, progress_callback=None):
    equipment_list = []
    image_urls = []
    total = len(url_list)

    for i, link in enumerate(url_list):
        html = requests.get(link)
        x = BeautifulSoup(html.content , 'html.parser')
        equipment_dictionary = {}

        title_tag = x.find('title')
        equipment_dictionary["Title"] = title_tag.get_text(strip=True)[5:] if title_tag else ''

        def get_text(tag_label):
            tag = x.find('b', string=tag_label)
            return tag.next_sibling.strip() if tag and tag.next_sibling else ''

        year = get_text('Year:')
        make = get_text('Make:')
        model = get_text('Model:')
        hours = get_text('Hours:')
        miles = get_text('Mileage:')

        equipment_dictionary["Year/Make/Model"] = f"{year} {make} {model}".strip()
        if hours and miles:
            equipment_dictionary["Hours/Miles"] = f"{hours} HOURS, {miles} MILES"
        elif hours:
            equipment_dictionary["Hours/Miles"] = f"{hours} HOURS"
        elif miles:
            equipment_dictionary["Hours/Miles"] = f"{miles} MILES"
        else:
            equipment_dictionary["Hours/Miles"] = ''

        # Try to find image URL
        first_img = x.select_one('.lot-carousel img')
        if first_img:
            zoom_src = first_img.get('data-zoom-src')
            if zoom_src:
                image_urls.append(zoom_src)

        equipment_list.append(equipment_dictionary)

        if progress_callback:
            progress_callback((i+1)/total)

    return equipment_list, image_urls


def Proxi_Bid(url_list, progress_callback=None):
    equipment_list = []
    image_urls = []
    total = len(url_list)

    def format_hours_miles(value):
        if not isinstance(value, str) or value.strip() == "":
            return value
        match = re.match(r"([\d,.]+)\s*(HOURS|MILES)", value, re.IGNORECASE)
        if match:
            num_str, unit = match.groups()
            try:
                num = round(float(num_str.replace(",", "")))
                return f"{num:,} {unit.upper()}"
            except ValueError:
                return value
        return value

    for i, link in enumerate(url_list):
        html = requests.get(link)
        soup = BeautifulSoup(html.content , 'html.parser')

        equipment_dictionary = {
            "Title": "",
            "Year/Make/Model": "",
            "Hours/Miles": ""
        }

        script_tag = soup.find('script', id='__NEXT_DATA__', type='application/json')
        if script_tag:
            try:
                data = json.loads(script_tag.string)
                lot = data.get("props", {}).get("pageProps", {}).get("lotDetails", {})

                # Title
                equipment_dictionary["Title"] = lot.get("title", "")

                # Year/Make/Model
                title_parts = lot.get("title", "").split()
                if title_parts:
                    year = title_parts[0] if title_parts[0].isdigit() else ''
                    make = title_parts[1] if len(title_parts) > 1 else ''
                    model = ' '.join(title_parts[2:]) if len(title_parts) > 2 else ''
                    equipment_dictionary["Year/Make/Model"] = f"{year} {make} {model}".strip()

                # Hours/Miles from description
                desc = lot.get("description", "")
                hours = ''
                miles = ''
                hours_match = re.search(r'([\d,]+\.\d+|[\d,]+)\s*Hours', desc, re.IGNORECASE)
                miles_match = re.search(r'([\d,]+\.\d+|[\d,]+)\s*Miles', desc, re.IGNORECASE)
                if hours_match:
                    hours = f"{hours_match.group(1)} HOURS"
                if miles_match:
                    miles = f"{miles_match.group(1)} MILES"

                if hours and miles:
                    equipment_dictionary["Hours/Miles"] = f"{hours}, {miles}"
                elif hours:
                    equipment_dictionary["Hours/Miles"] = hours
                elif miles:
                    equipment_dictionary["Hours/Miles"] = miles

                equipment_dictionary["Hours/Miles"] = format_hours_miles(equipment_dictionary["Hours/Miles"])

                # First image from imageUrls
                imgs = lot.get("imageUrls", [])
                if imgs and isinstance(imgs, list):
                    image_urls.append(imgs[0])
                elif lot.get("imageUrl"):
                    image_urls.append(lot["imageUrl"])

            except Exception as e:
                print(f"Error parsing JSON for {link}: {e}")

        equipment_list.append(equipment_dictionary)

        if progress_callback:
            progress_callback((i+1)/total)

    return equipment_list, image_urls


def Assiter(url_list, progress_callback=None):
    equipment_list = []
    image_urls = []
    total = len(url_list)

    def format_hours_miles(value):
        if not isinstance(value, str) or value.strip() == "":
            return value
        match = re.match(r"([\d,.]+)\s*(HOURS|MILES)", value, re.IGNORECASE)
        if match:
            num_str, unit = match.groups()
            try:
                num = round(float(num_str.replace(",", "")))
                return f"{num:,} {unit.upper()}"
            except ValueError:
                return value
        return value

    for i, link in enumerate(url_list):
        html = requests.get(link)
        soup = BeautifulSoup(html.content, 'html.parser')

        equipment_dictionary = {
            "Title": "",
            "Year/Make/Model": "",
            "Hours/Miles": ""
        }

        # Title from og:title
        title_meta = soup.find("meta", property="og:title")
        if title_meta and title_meta.get("content"):
            title_text = title_meta["content"].strip()
            equipment_dictionary["Title"] = title_text

            # Year/Make/Model split
            parts = [p for p in title_text.split() if p.strip()]
            year = parts[0] if parts and parts[0].isdigit() else ''
            make = ''
            model_start_index = 1
            if len(parts) > 1:
                make = parts[1]
                model_start_index = 2
                # Avoid duplicate makes
                if len(parts) > 2 and parts[1].lower() == parts[2].lower():
                    model_start_index = 3
            model = ' '.join(parts[model_start_index:]) if len(parts) > model_start_index else ''
            equipment_dictionary["Year/Make/Model"] = f"{year} {make} {model}".strip()

        # Mileage/Hours from og:description
        desc_meta = soup.find("meta", property="og:description")
        if desc_meta and desc_meta.get("content"):
            desc_text = desc_meta["content"]
            hours_match = re.search(r'([\d,]+\.\d+|[\d,]+)\s*Hours', desc_text, re.IGNORECASE)
            miles_match = re.search(r'Odo Reads:\s*([\d,]+\.\d+|[\d,]+)', desc_text, re.IGNORECASE)
            hours = f"{hours_match.group(1)} HOURS" if hours_match else ''
            miles = f"{miles_match.group(1)} MILES" if miles_match else ''
            if hours and miles:
                equipment_dictionary["Hours/Miles"] = f"{hours}, {miles}"
            elif hours:
                equipment_dictionary["Hours/Miles"] = hours
            elif miles:
                equipment_dictionary["Hours/Miles"] = miles

        # Format nicely
        equipment_dictionary["Hours/Miles"] = format_hours_miles(equipment_dictionary["Hours/Miles"])

        # First image from og:image
        img_meta = soup.find("meta", property="og:image")
        if img_meta and img_meta.get("content"):
            image_urls.append(img_meta["content"])

        equipment_list.append(equipment_dictionary)

        if progress_callback:
            progress_callback((i+1)/total)

    return equipment_list, image_urls


def Kerr_Mowrey_Witcher_Ritchason(url_list, progress_callback=None):
    equipment_list = []
    image_urls = []
    total = len(url_list)

    def format_hours_miles(value):
        if not isinstance(value, str) or value.strip() == "":
            return value
        match = re.match(r"([\d,.]+)\s*(HOURS|MILES)", value, re.IGNORECASE)
        if match:
            num_str, unit = match.groups()
            try:
                num = round(float(num_str.replace(",", "")))
                return f"{num:,} {unit.upper()}"
            except ValueError:
                return value
        return value

    for i, link in enumerate(url_list):
        html = requests.get(link)
        soup = BeautifulSoup(html.content, 'html.parser')

        equipment_dictionary = {
            "Title": "",
            "Year/Make/Model": "",
            "Hours/Miles": ""
        }

        # Title from og:title
        title_meta = soup.find("meta", property="og:title")
        if title_meta and title_meta.get("content"):
            title_text = title_meta["content"].strip()
            equipment_dictionary["Title"] = title_text

            # Improved Year/Make/Model split (same logic as Assiter)
            parts = [p for p in title_text.split() if p.strip()]
            year = parts[0] if parts and parts[0].isdigit() else ''
            make = ''
            model_start_index = 1
            if len(parts) > 1:
                make = parts[1]
                model_start_index = 2
                if len(parts) > 2 and parts[1].lower() == parts[2].lower():
                    model_start_index = 3
            model = ' '.join(parts[model_start_index:]) if len(parts) > model_start_index else ''
            equipment_dictionary["Year/Make/Model"] = f"{year} {make} {model}".strip()

        # Hours/Miles from og:description if present
        desc_meta = soup.find("meta", property="og:description")
        if desc_meta and desc_meta.get("content"):
            desc_text = desc_meta["content"]
            hours_match = re.search(r'([\d,]+\.\d+|[\d,]+)\s*(HOURS|HRS)', desc_text, re.IGNORECASE)
            miles_match = re.search(r'([\d,]+\.\d+|[\d,]+)\s*Miles', desc_text, re.IGNORECASE)
            hours = f"{hours_match.group(1)} HOURS" if hours_match else ''
            miles = f"{miles_match.group(1)} MILES" if miles_match else ''
            if hours and miles:
                equipment_dictionary["Hours/Miles"] = f"{hours}, {miles}"
            elif hours:
                equipment_dictionary["Hours/Miles"] = hours
            elif miles:
                equipment_dictionary["Hours/Miles"] = miles

        # Apply formatting
        equipment_dictionary["Hours/Miles"] = format_hours_miles(equipment_dictionary["Hours/Miles"])

        # First image from og:image
        img_meta = soup.find("meta", property="og:image")
        if img_meta and img_meta.get("content"):
            image_urls.append(img_meta["content"])

        equipment_list.append(equipment_dictionary)

        if progress_callback:
            progress_callback((i+1)/total)

    return equipment_list, image_urls


def Wausau(url_list, progress_callback=None):
    equipment_list = []
    image_urls = []
    total = len(url_list)

    def format_hours_miles(value):
        if not isinstance(value, str) or value.strip() == "":
            return value
        match = re.match(r"([\d,]+\.\d+|[\d,]+)\s*(HOURS|HRS|MILES)", value, re.IGNORECASE)
        if match:
            num_str, unit = match.groups()
            try:
                num = round(float(num_str.replace(",", "")))
                return f"{num:,} {unit.upper()}"
            except ValueError:
                return value
        return value

    for i, link in enumerate(url_list):
        html = requests.get(link)
        soup = BeautifulSoup(html.content, 'html.parser')

        equipment_dictionary = {
            "Title": "",
            "Year/Make/Model": "",
            "Hours/Miles": ""
        }

        # Get description text
        desc_meta = soup.find("meta", property="og:description")
        desc_text = desc_meta["content"].strip() if desc_meta and desc_meta.get("content") else ""

        # Use first comma‑separated chunk from description as the true Title
        if desc_text:
            main_title = desc_text.split(',')[0]  # before the first comma
            equipment_dictionary["Title"] = main_title

            # Year/Make/Model split
            parts = [p for p in main_title.split() if p.strip()]
            year = parts[0] if parts and parts[0].isdigit() else ''
            make = ''
            model_start_index = 1
            if len(parts) > 1:
                make = parts[1]
                model_start_index = 2
                # Avoid duplicate makes
                if len(parts) > 2 and parts[1].lower() == parts[2].lower():
                    model_start_index = 3
            model = ' '.join(parts[model_start_index:]) if len(parts) > model_start_index else ''
            equipment_dictionary["Year/Make/Model"] = f"{year} {make} {model}".strip()

            # Try to detect hours/miles in full description
            hours_match = re.search(r'([\d,]+\.\d+|[\d,]+)\s*(HOURS|HRS)', desc_text, re.IGNORECASE)
            miles_match = re.search(r'([\d,]+\.\d+|[\d,]+)\s*MILES', desc_text, re.IGNORECASE)
            hours = f"{hours_match.group(1)} HOURS" if hours_match else ''
            miles = f"{miles_match.group(1)} MILES" if miles_match else ''
            if hours and miles:
                equipment_dictionary["Hours/Miles"] = f"{hours}, {miles}"
            elif hours:
                equipment_dictionary["Hours/Miles"] = hours
            elif miles:
                equipment_dictionary["Hours/Miles"] = miles

        # Format Hours/Miles
        equipment_dictionary["Hours/Miles"] = format_hours_miles(equipment_dictionary["Hours/Miles"])

        # First image from og:image
        img_meta = soup.find("meta", property="og:image")
        if img_meta and img_meta.get("content"):
            image_urls.append(img_meta["content"])

        equipment_list.append(equipment_dictionary)

        if progress_callback:
            progress_callback((i+1)/total)

    return equipment_list, image_urls


# --------------------
# Streamlit App
# --------------------

st.title("Equipment Scraper App")
st.markdown("Instructions")
st.markdown("""
1. Upload a CSV file with one URL per row.
2. Select the website from the dropdown.
3. Click "Begin" to scrape.
4. Download results as Excel or a ZIP of images.
""")

# Initialize session state for buffers
if "excel_buffer" not in st.session_state:
    st.session_state.excel_buffer = None
if "zip_buffer" not in st.session_state:
    st.session_state.zip_buffer = None

uploaded_file = st.file_uploader("Upload a CSV file of URLs", type=["csv"])
website = st.selectbox("Select website type", ["Fastline", "Proxi_Bid", "Assiter", "Kerr", "Mowrey", "Witcher", "Wausau","Quarrick", "Superior Energy", 'Ritchason'])

if uploaded_file:
    df_input = pd.read_csv(uploaded_file, header=None)
    url_list = df_input.iloc[:, 0].tolist()
    st.markdown("Preview of URLs:")
    st.write(url_list[:3])

    if st.button("Begin"):
        st.subheader("Scraping Progress")
        progress_bar = st.progress(0)

        def update_progress(progress):
            progress_bar.progress(progress)

        with st.spinner("Scraping in progress..."):
            if website == 'Fastline':
                equipment_list, image_urls = Fastline(url_list, update_progress)
            elif website == "Proxi_Bid":
                equipment_list, image_urls = Proxi_Bid(url_list, update_progress)
            elif website == "Assiter":
                equipment_list, image_urls = Assiter(url_list, update_progress)
            elif website in ["Kerr", "Mowrey", "Witcher", 'Ritchason']:
                equipment_list, image_urls = Kerr_Mowrey_Witcher_Ritchason(url_list, update_progress)
            elif website == "Wausau":
                equipment_list, image_urls = Wausau(url_list, update_progress)
            elif website == 'Quarrick':
                equipment_list, image_urls = Proxi_Bid(url_list, update_progress)
            elif website == 'Superior Energy':
                equipment_list, image_urls = Proxi_Bid(url_list, update_progress)

        df_output = pd.DataFrame(equipment_list)
        
        # Format Hours/Miles column (round + commas)
        def format_hours_miles(value):
            if not isinstance(value, str) or value.strip() == "":
                return value
            match = re.match(r"([\d,.]+)\s*(HOURS|MILES)", value, re.IGNORECASE)
            if match:
                num_str, unit = match.groups()
                try:
                    num = round(float(num_str.replace(",", "")))
                    return f"{num:,} {unit.upper()}"
                except ValueError:
                    return value
            return value

        if "Hours/Miles" in df_output.columns:
            df_output["Hours/Miles"] = df_output["Hours/Miles"].apply(format_hours_miles)

        # Create Excel buffer
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            df_output.to_excel(writer, index=False, sheet_name="Scraped Data")
        excel_buffer.seek(0)
        st.session_state.excel_buffer = excel_buffer

        # Create ZIP buffer for images
        zip_buffer = io.BytesIO()
        if image_urls:
            with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                for i, url in enumerate(image_urls):
                    try:
                        img_data = requests.get(url).content
                        zip_file.writestr(f"image_{i+1}.jpg", img_data)
                    except Exception as e:
                        print(f"Failed to download {url}: {e}")
            zip_buffer.seek(0)
        st.session_state.zip_buffer = zip_buffer

        st.success("Scraping complete!")
if st.session_state.excel_buffer:
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="Download Excel",
            data=st.session_state.excel_buffer,
            file_name="scraped_equipment.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    with col2:
        st.download_button(
            label="Download Images (ZIP)",
            data=st.session_state.zip_buffer,
            file_name="equipment_images.zip",
            mime="application/zip"
        )
        
