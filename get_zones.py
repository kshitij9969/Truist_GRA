import time
import pdfplumber
import re
import pytesseract
import PIL
import requests
import io
import pandas as pd
import sys


def extract_text(file_name):
    with pdfplumber.open(file_name) as pdf:
        page = pdf.pages[2]
        text = page.extract_text()
    return text


def get_address(text):
    temp = re.findall(r"(Center)((.|\n)*)(\n3. LENDER)", text)
    temp = temp[0][1].lstrip(" ").replace("Atlanta,GA 30303 ", "")
    return " ".join([i.strip() for i in temp.split(" ")])


# Check below how the frame size is calculated
X_FRAME_RANGE = 19.33319367095828
Y_FRAME_RANGE = 18.661383852828294


def save_image(response):
    """
    Function to save images
    """
    image_bytes = io.BytesIO(response.content)
    img = PIL.Image.open(image_bytes)
    # img.save("Image.png")
    return img


def get_bbox(address):
    """
    Function to return address co-ordinates. 
    There are multiple candidates or multiple possible address matching the address 
    provided to the function. They are ranked according to the score. 
    Higher score means more confidence. 
    """

    params = (
        ('SingleLine', f'{address}'),
        ('f', 'json'),
        ('outSR', '{"wkid":102100,"latestWkid":3857}'),
        ('outFields', 'Loc_name,Country,Addr_type'),
    )
    response = requests.get(
        'https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates', params=params)
    data = response.json()
    extent = data['candidates'][0]['extent']
    location = data['candidates'][0]['location']
    x_min, x_max = location['x'] - X_FRAME_RANGE, location['x'] + X_FRAME_RANGE
    y_min, y_max = location['y'] - Y_FRAME_RANGE, location['y'] + Y_FRAME_RANGE
    return f'{x_min},{y_min},{x_max},{y_max}'


def extract_zone(image):
    """
    Function to extract zone from image
    """
    try:
        text = pytesseract.image_to_string(image, lang="eng")
        zone = re.findall(r'.*Zone.*\n', text)[0]
        zone = zone.lstrip("Zone")
    except Exception as e:
        return "Zone not found in image"
    return zone


def get_headers():
    headers = {
        'authority': 'hazards.fema.gov',
        'sec-ch-ua': '" Not;A Brand";v="99", "Google Chrome";v="97", "Chromium";v="97"',
        'sec-ch-ua-mobile': '?1',
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Mobile Safari/537.36',
        'sec-ch-ua-platform': '"Android"',
        'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'sec-fetch-site': 'same-site',
        'sec-fetch-mode': 'no-cors',
        'sec-fetch-dest': 'image',
        'referer': 'https://msc.fema.gov/',
        'accept-language': 'en-GB,en;q=0.9',
    }

    return headers


def get_params():
    params = (
        ('dpi', '96'),
        ('transparent', 'true'),
        ('format', 'png32'),
        ('bbox', get_bbox(address)),
        ('bboxSR', '102100'),
        ('imageSR', '102100'),
        ('size', '518,500'),
        ('f', 'image'),
    )

    return params


response = requests.get('https://hazards.fema.gov/gis/nfhl/rest/services/FIRMette/NFHLREST_FIRMette/MapServer/export',
                        headers=get_headers(), params=get_params())

image = save_image(response)

zone = extract_zone(image)
print("Zone is: ", zone)


filename = "SFHDF Example (1).pdf"

address = get_address(extract_text(filename))

file_name = f"{sys.argv[1]}"

# df = pd.DataFrame(COORDINATES, columns=['lat', 'long', 'address'])
df = pd.read_csv(file_name)
df['Region'] = df['address'].apply(lambda x: x.split(",")[-3])

result = []


data = df[:100].values.tolist()

start_time = time.time()

total = 0

for index, row in enumerate(data):
    print(index)
    address = row[2]
    print(address)
    t1 = time.time()
    response = requests.get('https://hazards.fema.gov/gis/nfhl/rest/services/FIRMette/NFHLREST_FIRMette/MapServer/export',
                            headers=get_headers(), params=get_params())
    image = save_image(response)
    zone = extract_zone(image)
    total += (time.time() - t1)
    print("Zone is: ", zone)
    result.append(zone)

end_time = time.time()
print("Total time taken: ", end_time - start_time)
print("Average time taken: ", (end_time - start_time) / len(df))

df['Zone'] = zone
