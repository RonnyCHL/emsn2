#!/usr/bin/env python3
"""
EMSN Species Images Module
Fetches bird photos from Wikimedia Commons for report enhancement
"""

import requests
import re
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote
import time

# Cache directory for downloaded images
CACHE_DIR = Path("/mnt/nas-reports/species-images")

# Wikimedia Commons API
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# Required User-Agent header for Wikimedia API
# See: https://meta.wikimedia.org/wiki/User-Agent_policy
HEADERS = {
    'User-Agent': 'EMSN-BirdReports/1.0 (https://www.ronnyhullegie.nl; emsn@ronnyhullegie.nl) Python/requests'
}

# Dutch to scientific name mapping for common species (for better search results)
SPECIES_MAPPING = {
    'Koolmees': 'Parus major',
    'Pimpelmees': 'Cyanistes caeruleus',
    'Merel': 'Turdus merula',
    'Roodborst': 'Erithacus rubecula',
    'Huismus': 'Passer domesticus',
    'Vink': 'Fringilla coelebs',
    'Zanglijster': 'Turdus philomelos',
    'Ekster': 'Pica pica',
    'Houtduif': 'Columba palumbus',
    'Kauw': 'Coloeus monedula',
    'Zwarte Kraai': 'Corvus corone',
    'Spreeuw': 'Sturnus vulgaris',
    'Groenling': 'Chloris chloris',
    'Heggenmus': 'Prunella modularis',
    'Winterkoning': 'Troglodytes troglodytes',
    'Boomkruiper': 'Certhia brachydactyla',
    'Boomklever': 'Sitta europaea',
    'Grote Bonte Specht': 'Dendrocopos major',
    'Gaai': 'Garrulus glandarius',
    'Tjiftjaf': 'Phylloscopus collybita',
    'Zwartkop': 'Sylvia atricapilla',
    'Fitis': 'Phylloscopus trochilus',
    'Gierzwaluw': 'Apus apus',
    'Boerenzwaluw': 'Hirundo rustica',
    'Huiszwaluw': 'Delichon urbicum',
    'Koekoek': 'Cuculus canorus',
    'Tortelduif': 'Streptopelia turtur',
    'Turkse Tortel': 'Streptopelia decaocto',
    'Fazant': 'Phasianus colchicus',
    'Scholekster': 'Haematopus ostralegus',
    'Kievit': 'Vanellus vanellus',
    'Grutto': 'Limosa limosa',
    'Wulp': 'Numenius arquata',
    'Meerkoet': 'Fulica atra',
    'Waterhoen': 'Gallinula chloropus',
    'Wilde Eend': 'Anas platyrhynchos',
    'Kuifeend': 'Aythya fuligula',
    'Blauwe Reiger': 'Ardea cinerea',
    'Buizerd': 'Buteo buteo',
    'Sperwer': 'Accipiter nisus',
    'Torenvalk': 'Falco tinnunculus',
    'Bosuil': 'Strix aluco',
    'Ransuil': 'Asio otus',
    'Kerkuil': 'Tyto alba',
    'IJsvogel': 'Alcedo atthis',
    'Groene Specht': 'Picus viridis',
    'Zwarte Specht': 'Dryocopus martius',
    'Staartmees': 'Aegithalos caudatus',
    'Kuifmees': 'Lophophanes cristatus',
    'Glanskop': 'Poecile palustris',
    'Matkop': 'Poecile montanus',
    'Ringmus': 'Passer montanus',
    'Grauwe Vliegenvanger': 'Muscicapa striata',
    'Bonte Vliegenvanger': 'Ficedula hypoleuca',
    'Rietgors': 'Emberiza schoeniclus',
    'Geelgors': 'Emberiza citrinella',
    'Appelvink': 'Coccothraustes coccothraustes',
    'Putter': 'Carduelis carduelis',
    'Sijs': 'Spinus spinus',
    'Kneu': 'Linaria cannabina',
    'Kruisbek': 'Loxia curvirostra',
    'Keep': 'Fringilla montifringilla',
    'Koperwiek': 'Turdus iliacus',
    'Kramsvogel': 'Turdus pilaris',
    'Grote Lijster': 'Turdus viscivorus',
    'Goudhaantje': 'Regulus regulus',
    'Vuurgoudhaan': 'Regulus ignicapilla',
    'Nachtegaal': 'Luscinia megarhynchos',
    'Blauwborst': 'Luscinia svecica',
    'Gekraagde Roodstaart': 'Phoenicurus phoenicurus',
    'Zwarte Roodstaart': 'Phoenicurus ochruros',
    'Tapuit': 'Oenanthe oenanthe',
    'Rietzanger': 'Acrocephalus schoenobaenus',
    'Kleine Karekiet': 'Acrocephalus scirpaceus',
    'Grasmus': 'Curruca communis',
    'Tuinfluiter': 'Sylvia borin',
    'Spotvogel': 'Hippolais icterina',
    'Wielewaal': 'Oriolus oriolus',
    # Ganzen
    'Kolgans': 'Anser albifrons',
    'Grauwe Gans': 'Anser anser',
    'Brandgans': 'Branta leucopsis',
    'Canadese Gans': 'Branta canadensis',
    'Nijlgans': 'Alopochen aegyptiaca',
    'Grote Canadese Gans': 'Branta canadensis',
    # Extra soorten
    'Kleine Bonte Specht': 'Dryobates minor',
    'Graspieper': 'Anthus pratensis',
    'Boompieper': 'Anthus trivialis',
    'Witte Kwikstaart': 'Motacilla alba',
    'Gele Kwikstaart': 'Motacilla flava',
    'Grote Gele Kwikstaart': 'Motacilla cinerea',
    'Aalscholver': 'Phalacrocorax carbo',
    'Fuut': 'Podiceps cristatus',
    'Ooievaar': 'Ciconia ciconia',
    'Lepelaar': 'Platalea leucorodia',
    'Roek': 'Corvus frugilegus',
    'Raaf': 'Corvus corax',
    'Roerdomp': 'Botaurus stellaris',
    'Kleine Zilverreiger': 'Egretta garzetta',
    'Grote Zilverreiger': 'Ardea alba',
}


def get_scientific_name(dutch_name: str) -> str:
    """Get scientific name for a Dutch bird name"""
    return SPECIES_MAPPING.get(dutch_name, dutch_name)


def search_commons_image(species_name: str, scientific_name: str = None) -> Optional[Dict]:
    """
    Search Wikimedia Commons for a bird image.

    Uses a strict search strategy to avoid incorrect species:
    1. First tries to find images in the species-specific Wikimedia category
    2. Falls back to search with scientific name only (not common name)
    3. Validates that filenames contain the scientific name

    Args:
        species_name: Dutch or English common name
        scientific_name: Scientific name (Latin binomial)

    Returns:
        Dict with image info or None
    """
    if not scientific_name:
        scientific_name = get_scientific_name(species_name)

    if not scientific_name or scientific_name == species_name:
        print(f"   WARNING: No scientific name for {species_name}, skipping image search")
        return None

    # Extract genus and species from scientific name (e.g., "Parus major" -> "Parus", "major")
    sci_parts = scientific_name.split()
    if len(sci_parts) < 2:
        return None
    genus, species_epithet = sci_parts[0], sci_parts[1]

    # Strategy 1: Search in the species category (most accurate)
    try:
        # Wikimedia Commons uses category names like "Category:Parus major"
        category_name = f"Category:{scientific_name.replace(' ', '_')}"

        params = {
            'action': 'query',
            'format': 'json',
            'list': 'categorymembers',
            'cmtitle': category_name,
            'cmtype': 'file',
            'cmlimit': 10,
        }

        response = requests.get(COMMONS_API, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()

        members = data.get('query', {}).get('categorymembers', [])

        for member in members:
            title = member.get('title', '')
            # Skip non-image files
            if not any(title.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png']):
                continue
            # Skip diagrams, maps, stamps, eggs, nests, etc
            skip_words = ['stamp', 'map', 'diagram', 'drawing', 'illustration', 'logo',
                         'icon', 'egg', 'nest', 'skeleton', 'skull', 'feather', 'track',
                         'distribution', 'range', 'habitat']
            if any(word in title.lower() for word in skip_words):
                continue

            # Get image info
            image_info = get_image_info(title)
            if image_info:
                print(f"      Found in category: {title[:50]}...")
                return image_info

        time.sleep(0.5)

    except Exception as e:
        print(f"   WARNING: Category search failed for {scientific_name}: {e}")

    # Strategy 2: Direct search with scientific name (fallback)
    try:
        params = {
            'action': 'query',
            'format': 'json',
            'list': 'search',
            'srsearch': f'"{scientific_name}"',  # Exact phrase match
            'srnamespace': 6,  # File namespace
            'srlimit': 10,
        }

        response = requests.get(COMMONS_API, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()

        results = data.get('query', {}).get('search', [])

        for result in results:
            title = result.get('title', '')
            title_lower = title.lower()

            # Skip non-image files
            if not any(title_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png']):
                continue

            # Skip diagrams, maps, stamps, eggs, etc
            skip_words = ['stamp', 'map', 'diagram', 'drawing', 'illustration', 'logo',
                         'icon', 'egg', 'nest', 'skeleton', 'skull', 'feather', 'track',
                         'distribution', 'range', 'habitat']
            if any(word in title_lower for word in skip_words):
                continue

            # IMPORTANT: Verify filename contains scientific name parts
            # This prevents returning wrong species
            if genus.lower() not in title_lower and species_epithet.lower() not in title_lower:
                continue

            # Get image info
            image_info = get_image_info(title)
            if image_info:
                print(f"      Found via search: {title[:50]}...")
                return image_info

    except Exception as e:
        print(f"   WARNING: Search failed for {scientific_name}: {e}")

    return None


def get_image_info(file_title: str) -> Optional[Dict]:
    """
    Get detailed info about a Wikimedia Commons image.

    Args:
        file_title: The file title (including 'File:' prefix)

    Returns:
        Dict with url, thumb_url, attribution, license
    """
    try:
        params = {
            'action': 'query',
            'format': 'json',
            'titles': file_title,
            'prop': 'imageinfo',
            'iiprop': 'url|user|license|extmetadata',
            'iiurlwidth': 400,  # Thumbnail width
        }

        response = requests.get(COMMONS_API, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()

        pages = data.get('query', {}).get('pages', {})
        for page_id, page_data in pages.items():
            if page_id == '-1':
                continue

            image_info = page_data.get('imageinfo', [{}])[0]
            extmeta = image_info.get('extmetadata', {})

            # Get license info
            license_short = extmeta.get('LicenseShortName', {}).get('value', 'Unknown')
            artist = extmeta.get('Artist', {}).get('value', image_info.get('user', 'Unknown'))
            # Clean HTML from artist
            artist = re.sub(r'<[^>]+>', '', artist).strip()

            return {
                'title': file_title.replace('File:', ''),
                'url': image_info.get('url'),
                'thumb_url': image_info.get('thumburl'),
                'thumb_width': image_info.get('thumbwidth'),
                'thumb_height': image_info.get('thumbheight'),
                'user': image_info.get('user'),
                'artist': artist,
                'license': license_short,
                'description_url': image_info.get('descriptionurl'),
            }

    except Exception as e:
        print(f"   WARNING: Could not get image info for {file_title}: {e}")

    return None


def download_image(image_info: Dict, species_name: str) -> Optional[Path]:
    """
    Download and cache an image.

    Args:
        image_info: Dict from get_image_info()
        species_name: Species name for filename

    Returns:
        Path to downloaded image or None
    """
    if not image_info or not image_info.get('thumb_url'):
        return None

    # Create cache directory
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Clean species name for filename
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', species_name.lower())
    ext = Path(image_info['title']).suffix or '.jpg'
    cache_file = CACHE_DIR / f"{safe_name}{ext}"

    # Return cached file if exists
    if cache_file.exists():
        return cache_file

    try:
        response = requests.get(image_info['thumb_url'], headers=HEADERS, timeout=30)
        response.raise_for_status()

        with open(cache_file, 'wb') as f:
            f.write(response.content)

        return cache_file

    except Exception as e:
        print(f"   WARNING: Could not download image for {species_name}: {e}")
        return None


def get_species_image(dutch_name: str, scientific_name: str = None) -> Optional[Dict]:
    """
    Get an image for a species (with caching).

    Args:
        dutch_name: Dutch common name
        scientific_name: Scientific name (optional, will be looked up if not provided)

    Returns:
        Dict with local_path, attribution, license, source_url
    """
    if not scientific_name:
        scientific_name = get_scientific_name(dutch_name)

    # Check cache first
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', dutch_name.lower())
    for ext in ['.jpg', '.jpeg', '.png']:
        cache_file = CACHE_DIR / f"{safe_name}{ext}"
        if cache_file.exists():
            # Return cached (we'd need to store attribution separately for full solution)
            return {
                'local_path': str(cache_file),
                'cached': True,
            }

    # Search and download
    image_info = search_commons_image(dutch_name, scientific_name)
    if not image_info:
        return None

    local_path = download_image(image_info, dutch_name)
    if not local_path:
        return None

    return {
        'local_path': str(local_path),
        'attribution': image_info.get('artist', 'Unknown'),
        'license': image_info.get('license', 'Unknown'),
        'source_url': image_info.get('description_url'),
        'cached': False,
    }


def get_images_for_species_list(species_list: List[Dict], max_images: int = 5) -> List[Dict]:
    """
    Get images for a list of species (e.g., top species from report).

    Args:
        species_list: List of dicts with 'name' and optionally 'scientific_name'
        max_images: Maximum number of images to fetch

    Returns:
        List of dicts with species info + image info
    """
    results = []

    for species in species_list[:max_images]:
        name = species.get('name', '')
        scientific = species.get('scientific_name', '')

        print(f"   Zoeken afbeelding: {name}...")
        image = get_species_image(name, scientific)

        if image:
            results.append({
                'name': name,
                'scientific_name': scientific,
                'image': image,
            })
            print(f"      ✓ Gevonden: {Path(image['local_path']).name}")
        else:
            print(f"      ✗ Geen afbeelding gevonden")

        # Rate limiting
        time.sleep(1)

    return results


def generate_species_gallery_markdown(species_with_images: List[Dict]) -> str:
    """
    Generate markdown for a species image gallery.

    Args:
        species_with_images: Output from get_images_for_species_list()

    Returns:
        Markdown string
    """
    if not species_with_images:
        return ""

    markdown = "## Soorten in Beeld\n\n"
    markdown += "<div class=\"species-gallery\">\n\n"

    for item in species_with_images:
        name = item['name']
        scientific = item.get('scientific_name', '')
        image = item.get('image', {})

        if not image or not image.get('local_path'):
            continue

        # Use relative path for markdown
        img_path = Path(image['local_path']).name

        markdown += f"### {name}"
        if scientific and scientific != name:
            markdown += f" (*{scientific}*)"
        markdown += "\n\n"

        markdown += f"![{name}](species-images/{img_path})\n\n"

        # Attribution
        if image.get('attribution'):
            markdown += f"*Foto: {image['attribution']}"
            if image.get('license'):
                markdown += f" ({image['license']})"
            markdown += "*\n\n"

    markdown += "</div>\n\n"

    return markdown


# Test
if __name__ == "__main__":
    print("Testing species images module...")

    test_species = [
        {'name': 'Koolmees', 'scientific_name': 'Parus major'},
        {'name': 'Merel', 'scientific_name': 'Turdus merula'},
        {'name': 'Roodborst', 'scientific_name': 'Erithacus rubecula'},
    ]

    results = get_images_for_species_list(test_species, max_images=3)

    print(f"\nGevonden: {len(results)} afbeeldingen")
    for r in results:
        print(f"  - {r['name']}: {Path(r['image']['local_path']).name}")

    print("\n" + "="*60)
    print("\nMarkdown output:")
    print(generate_species_gallery_markdown(results))
