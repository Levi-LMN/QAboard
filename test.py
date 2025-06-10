import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def count_pages(start_url, max_pages=100):
    visited = set()
    to_visit = [start_url]
    domain = urlparse(start_url).netloc

    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue
        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                continue
            visited.add(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                full_url = urljoin(url, link['href'])
                if urlparse(full_url).netloc == domain and full_url not in visited:
                    to_visit.append(full_url)
        except Exception as e:
            continue

    return len(visited)

# Example usage
url = "https://infonet-biovision.org/"
print(f"Estimated number of pages: {count_pages(url)}")
