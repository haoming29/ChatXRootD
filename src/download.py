import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime


def download_pdf(url, folder="data"):
    # Ensure the folder exists
    os.makedirs(folder, exist_ok=True)

    # Get the HTML content of the page
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Find all the <a> tags
    links = soup.find_all("a")

    # Filter links that end with .pdf
    pdf_links = [link["href"] for link in links if link["href"].endswith(".pdf")]

    # Download each PDF
    for link in pdf_links:
        # Handle relative URLs by creating a full URL from the base
        if link.startswith("/"):
            full_url = f"{url.rsplit('/', 1)[0]}{link}"
        elif not link.startswith("http"):
            full_url = f"{url.rsplit('/', 1)[0]}/{link}"
        else:
            full_url = link

        # Get the PDF content
        pdf_response = requests.get(full_url)

        # Create a filename with the current datetime
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{link.split('/')[-1].replace('.pdf', '')}_{timestamp}.pdf"
        file_path = os.path.join(folder, filename)

        # Ensure unique filename by checking for collisions
        counter = 1
        while os.path.exists(file_path):
            file_path = os.path.join(
                folder, f"{filename.replace('.pdf', '')}_{counter}.pdf"
            )
            counter += 1

        # Save the PDF
        with open(file_path, "wb") as f:
            f.write(pdf_response.content)
        print(f"Downloaded {file_path}")


download_pdf("https://xrootd.slac.stanford.edu/docs.html")
