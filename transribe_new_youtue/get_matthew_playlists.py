import requests
from bs4 import BeautifulSoup
import json
import re
import os
import codecs

def ensure_valid_filename(filename):
    """Ensure the filename is valid and has correct extension"""
    # Remove invalid characters
    valid_name = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.'))
    valid_name = valid_name.strip()
    return valid_name

def save_file(content, filename, file_type='txt'):
    """Save content to file with proper error handling"""
    try:
        # Ensure the filename has the correct extension
        if not filename.endswith(f'.{file_type}'):
            filename = f"{filename}.{file_type}"
        
        # Make filename safe
        valid_name = "".join(c if c.isalnum() or c in ' -_.' else '_' for c in filename).strip()
        
        print(f"\nSaving to file: {valid_name}")
        
        # For binary content (HTML, raw response)
        if isinstance(content, bytes):
            with open(valid_name, 'wb') as f:
                f.write(content)
            return True
            
        # For JSON content
        if file_type == 'json':
            with open(valid_name, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2, ensure_ascii=False)
            return True
            
        # For text content
        with open(valid_name, 'w', encoding='utf-8', errors='replace') as f:
            f.write(str(content))
        return True
            
    except Exception as e:
        print(f"Error saving file {filename}: {str(e)}")
        return False

def read_file(filename):
    """Read file content with proper error handling"""
    try:
        # Try UTF-8 first
        try:
            with codecs.open(filename, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # If UTF-8 fails, try UTF-16
            with codecs.open(filename, 'r', encoding='utf-16') as f:
                return f.read()
    except Exception as e:
        print(f"Error reading file {filename}: {str(e)}")
        return None

def get_playlists(channel_url):
    playlists = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1'
    }
    
    cookies = {
        'CONSENT': 'YES+cb.20240214-11-p0.en+FX+119',
        'SOCS': 'CAESEwgDEgk0ODE1OTI4NjAaAmVuIAEaBgiA_LyaBg',
        'wide': '1'
    }
    
    if not channel_url.endswith('/playlists'):
        channel_url = channel_url.rstrip('/') + '/playlists'
    
    print(f"\nFetching playlists from: {channel_url}")
    try:
        response = requests.get(channel_url, headers=headers, cookies=cookies)
        response.raise_for_status()
        
        # Save raw response bytes
        save_file(response.content, "raw_response.txt")
        
        # Convert content for processing
        content = response.content.decode('utf-8', errors='replace')
        
        if 'consent.youtube.com' in content:
            print("\nGot consent page instead of channel page. Please visit the channel in your browser first.")
            return playlists
        
        # Save HTML content
        save_file(response.content, "youtube_channel.html")
        
        # Try to parse with BeautifulSoup first (using lxml parser)
        print("\nParsing with BeautifulSoup...")
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Look for ytInitialData in script tags
        for script in soup.find_all('script'):
            if script.string and 'var ytInitialData = ' in script.string:
                json_str = script.string.split('var ytInitialData = ')[1].split(';</script>')[0]
                try:
                    data = json.loads(json_str)
                    save_file(data, "yt_data.json")
                    
                    # Look for playlists in tabs
                    tabs = data.get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs', [])
                    for tab in tabs:
                        if 'tabRenderer' in tab and tab['tabRenderer'].get('title') == 'Playlists':
                            print("\nFound playlists tab")
                            grid_items = tab['tabRenderer'].get('content', {}).get('sectionListRenderer', {}).get('contents', [{}])[0].get('itemSectionRenderer', {}).get('contents', [{}])[0].get('gridRenderer', {}).get('items', [])
                            
                            for item in grid_items:
                                if 'gridPlaylistRenderer' in item:
                                    playlist_data = item['gridPlaylistRenderer']
                                    playlist_id = playlist_data.get('playlistId', '')
                                    title = ' '.join(t.get('text', '') for t in playlist_data.get('title', {}).get('runs', []))
                                    video_count = playlist_data.get('videoCount', {}).get('simpleText', '0 videos')
                                    
                                    if playlist_id and title:
                                        playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                                        playlists.append({
                                            'url': playlist_url,
                                            'id': playlist_id,
                                            'title': title,
                                            'video_count': video_count
                                        })
                                        print(f"\nFound playlist: {title}")
                                        print(f"Video count: {video_count}")
                                        print(f"URL: {playlist_url}")
                except Exception as e:
                    print(f"Error parsing JSON from script tag: {str(e)}")
                    continue
        
        # If no playlists found, try direct HTML parsing
        if not playlists:
            print("\nTrying direct HTML parsing...")
            
            # Look for playlist elements
            playlist_elements = soup.find_all(['ytd-grid-playlist-renderer', 'ytd-playlist-renderer'])
            for element in playlist_elements:
                try:
                    playlist_link = element.find('a', href=True)
                    if playlist_link and 'playlist?list=' in playlist_link['href']:
                        playlist_id = playlist_link['href'].split('list=')[1].split('&')[0]
                        title_elem = element.find(['yt-formatted-string', 'span'], {'class': 'title'})
                        title = title_elem.text.strip() if title_elem else f"Playlist_{playlist_id}"
                        
                        playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                        if playlist_url not in [p['url'] for p in playlists]:
                            playlists.append({
                                'url': playlist_url,
                                'id': playlist_id,
                                'title': title
                            })
                            print(f"\nFound playlist: {title}")
                            print(f"URL: {playlist_url}")
                except Exception as e:
                    print(f"Error processing playlist element: {str(e)}")
                    continue
        
        # If still no playlists, try regex as last resort
        if not playlists:
            print("\nTrying regex search...")
            playlist_matches = re.findall(r'href="(/playlist\?list=[^"]+)".*?title="([^"]+)"', content)
            for href, title in playlist_matches:
                playlist_id = href.split('list=')[1].split('&')[0] if '&' in href else href.split('list=')[1]
                playlist_url = f"https://www.youtube.com{href}"
                if playlist_url not in [p['url'] for p in playlists]:
                    playlists.append({
                        'url': playlist_url,
                        'id': playlist_id,
                        'title': title
                    })
                    print(f"\nFound playlist: {title}")
                    print(f"URL: {playlist_url}")
    
    except requests.RequestException as e:
        print(f"Error fetching channel: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
    
    print(f"\nFound {len(playlists)} playlists in total")
    return playlists

if __name__ == "__main__":
    channel_url = "https://www.youtube.com/@matthew_berman/playlists"
    playlists = get_playlists(channel_url)
    
    if playlists:
        save_file(playlists, "playlists.json")
        print("\nSaved playlists to playlists.json")
    else:
        print("\nNo playlists were found to save") 