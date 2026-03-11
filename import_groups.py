import os
from bs4 import BeautifulSoup
from models import FBGroup
from database import SessionLocal
import re

def import_groups(html_file):
    if not os.path.exists(html_file):
        print(f"File not found: {html_file}")
        return

    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'lxml')
    items = soup.find_all('div', role='listitem')
    
    db = SessionLocal()
    count = 0
    
    for item in items:
        # Looking for the group link which contains the name and URL
        # Usually looking for href with /groups/ and some text
        link_tag = item.find('a', href=re.compile(r'facebook\.com/groups/'))
        if not link_tag:
            continue
            
        url = link_tag['href']
        # Clean up URL (remove trailing slashes or query params if any)
        url = url.split('?')[0].rstrip('/')
        if not url.endswith('/'):
            url += '/'

        # Name is usually in the same link tag or a nested span
        name = link_tag.get_text(strip=True)
        if not name:
            # Fallback: look for other a tags with text if the first one was an image link
            all_links = item.find_all('a', href=re.compile(r'facebook\.com/groups/'))
            for l in all_links:
                if l.get_text(strip=True):
                    name = l.get_text(strip=True)
                    break

        if not name:
            name = "Unknown Group"

        # Check if exists
        existing = db.query(FBGroup).filter(FBGroup.facebook == url).first()
        if not existing:
            new_group = FBGroup(name=name, facebook=url)
            db.add(new_group)
            count += 1
            print(f"Adding: {name} ({url})")
        else:
            print(f"Skipping (already exists): {name}")

    db.commit()
    db.close()
    print(f"Imported {count} new groups.")

if __name__ == "__main__":
    import_groups("data/joined-group-list.html")
