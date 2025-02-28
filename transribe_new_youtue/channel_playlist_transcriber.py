from youtube_transcript_api import YouTubeTranscriptApi
import re
from urllib.parse import urlparse, parse_qs
import requests
import os
import time
from bs4 import BeautifulSoup
import json
from playlist_transcriber import get_playlist_videos, download_video_transcript, get_safe_filename

def get_channel_name(channel_url):
    """Get channel name from URL or page"""
    try:
        # Extract channel name from URL first
        if '/@' in channel_url:
            channel_name = channel_url.split('/@')[1].split('/')[0]
            return channel_name
        
        # If not in URL, fetch from page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        response = requests.get(channel_url, headers=headers)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to get channel name from meta tags
            meta_title = soup.find('meta', {'property': 'og:title'})
            if meta_title:
                return meta_title['content'].strip()
            
            # Try to get from title
            title = soup.find('title')
            if title:
                channel_name = title.text.replace(' - YouTube', '').strip()
                return channel_name
    
    except Exception as e:
        print(f"Error getting channel name: {str(e)}")
    
    return "Unknown_Channel"

def get_playlists(channel_url):
    """Get all playlists from a channel"""
    playlists = []
    try:
        # Ensure URL ends with /playlists
        if not channel_url.endswith('/playlists'):
            channel_url = channel_url.rstrip('/') + '/playlists'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        print(f"\nFetching playlists from: {channel_url}")
        response = requests.get(channel_url, headers=headers)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Save HTML for debugging
            with open("mathew.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            print("\nSaved HTML to mathew.html for debugging")
            
            # Look for ytInitialData
            print("\nLooking for playlist data...")
            for script in soup.find_all('script'):
                if script.string and 'var ytInitialData = ' in script.string:
                    print("Found ytInitialData")
                    # Extract the JSON data
                    data_text = script.string
                    start_idx = data_text.find('var ytInitialData = ') + len('var ytInitialData = ')
                    end_idx = data_text.find(';</script>', start_idx)
                    
                    if start_idx > 0 and end_idx > 0:
                        try:
                            data = json.loads(data_text[start_idx:end_idx])
                            
                            # Save raw data for debugging
                            with open("yt_data.json", "w", encoding="utf-8") as f:
                                json.dump(data, f, indent=2)
                            print("Saved raw data to yt_data.json")
                            
                            # Extract playlists recursively from the data
                            def extract_playlists_from_data(obj):
                                if isinstance(obj, dict):
                                    # Check for playlist renderer
                                    if 'playlistRenderer' in obj:
                                        playlist_data = obj['playlistRenderer']
                                        playlist_id = playlist_data.get('playlistId', '')
                                        title = ''
                                        
                                        # Extract title
                                        title_obj = playlist_data.get('title', {})
                                        if isinstance(title_obj, dict):
                                            if 'runs' in title_obj:
                                                title = ' '.join(t.get('text', '') for t in title_obj['runs'])
                                            elif 'simpleText' in title_obj:
                                                title = title_obj['simpleText']
                                        
                                        if playlist_id and title:
                                            playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                                            if playlist_url not in [p['url'] for p in playlists]:
                                                playlists.append({
                                                    'url': playlist_url,
                                                    'id': playlist_id,
                                                    'title': title
                                                })
                                                print(f"Found playlist: {title} ({playlist_url})")
                                    
                                    # Check for grid playlist renderer
                                    elif 'gridPlaylistRenderer' in obj:
                                        playlist_data = obj['gridPlaylistRenderer']
                                        playlist_id = playlist_data.get('playlistId', '')
                                        title = ''
                                        
                                        # Extract title
                                        title_obj = playlist_data.get('title', {})
                                        if isinstance(title_obj, dict):
                                            if 'runs' in title_obj:
                                                title = ' '.join(t.get('text', '') for t in title_obj['runs'])
                                            elif 'simpleText' in title_obj:
                                                title = title_obj['simpleText']
                                        
                                        if playlist_id and title:
                                            playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                                            if playlist_url not in [p['url'] for p in playlists]:
                                                playlists.append({
                                                    'url': playlist_url,
                                                    'id': playlist_id,
                                                    'title': title
                                                })
                                                print(f"Found playlist: {title} ({playlist_url})")
                                    
                                    # Recursively search all values
                                    for value in obj.values():
                                        if isinstance(value, (dict, list)):
                                            extract_playlists_from_data(value)
                                
                                elif isinstance(obj, list):
                                    for item in obj:
                                        if isinstance(item, (dict, list)):
                                            extract_playlists_from_data(item)
                            
                            # Start recursive extraction
                            extract_playlists_from_data(data)
                            
                        except json.JSONDecodeError as e:
                            print(f"Error parsing JSON: {str(e)}")
                            continue
            
            # If no playlists found through ytInitialData, try HTML parsing
            if not playlists:
                print("\nTrying HTML parsing method...")
                # Look for playlist links
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if 'playlist?list=' in href:
                        playlist_id = href.split('list=')[1].split('&')[0]
                        # Try to get title from parent elements
                        title_elem = link.find(['span', 'yt-formatted-string', 'div'], {'class': 'title'})
                        title = title_elem.text if title_elem else f"Playlist_{playlist_id}"
                        
                        playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                        if playlist_url not in [p['url'] for p in playlists]:
                            playlists.append({
                                'url': playlist_url,
                                'id': playlist_id,
                                'title': title
                            })
                            print(f"Found playlist: {title} ({playlist_url})")
            
            print(f"\nFound {len(playlists)} playlists in total")
            
        else:
            print(f"Error accessing channel: {response.status_code}")
    
    except Exception as e:
        print(f"Error getting playlists: {str(e)}")
    
    return playlists

def process_channel_playlists(channel_url):
    """Process all playlists from a channel"""
    try:
        # Get channel name
        channel_name = get_channel_name(channel_url)
        safe_channel_name = get_safe_filename(channel_name)
        print(f"\nProcessing channel: {channel_name}")
        
        # Create channel directory
        if not os.path.exists(safe_channel_name):
            os.makedirs(safe_channel_name)
        
        # Get all playlists
        playlists = get_playlists(channel_url)
        
        if not playlists:
            print("No playlists found in the channel.")
            return
        
        total_playlists = len(playlists)
        successful_playlists = 0
        failed_playlists = 0
        
        # Process each playlist
        for i, playlist in enumerate(playlists, 1):
            print(f"\nProcessing playlist {i}/{total_playlists}: {playlist['title']}")
            
            try:
                # Create playlist directory
                safe_playlist_name = get_safe_filename(playlist['title'])
                playlist_dir = os.path.join(safe_channel_name, safe_playlist_name)
                if not os.path.exists(playlist_dir):
                    os.makedirs(playlist_dir)
                
                # Get videos from playlist
                videos = get_playlist_videos(playlist['id'])
                
                if not videos:
                    print(f"No videos found in playlist: {playlist['title']}")
                    failed_playlists += 1
                    continue
                
                successful_videos = 0
                failed_videos = 0
                
                # Process each video
                for j, video_url in enumerate(videos, 1):
                    print(f"\nProcessing video {j}/{len(videos)}")
                    if download_video_transcript(video_url, playlist_dir):
                        successful_videos += 1
                    else:
                        failed_videos += 1
                    time.sleep(1)  # Add delay to avoid rate limiting
                
                print(f"\nPlaylist complete: {playlist['title']}")
                print(f"Successfully downloaded: {successful_videos} transcripts")
                print(f"Failed to download: {failed_videos} transcripts")
                
                if successful_videos > 0:
                    successful_playlists += 1
                else:
                    failed_playlists += 1
                
            except Exception as e:
                print(f"Error processing playlist {playlist['title']}: {str(e)}")
                failed_playlists += 1
            
            print(f"\nProgress: {i}/{total_playlists} playlists processed")
        
        print(f"\nChannel processing complete: {channel_name}")
        print(f"Successfully processed: {successful_playlists} playlists")
        print(f"Failed to process: {failed_playlists} playlists")
        print(f"All transcripts are saved in the '{safe_channel_name}' directory")
        
    except Exception as e:
        print(f"Error processing channel: {str(e)}")

def get_playlist_id(url):
    """Extract playlist ID from YouTube URL"""
    try:
        parsed_url = urlparse(url)
        if 'list=' in url:
            return parse_qs(parsed_url.query)['list'][0]
    except Exception as e:
        print(f"Error extracting playlist ID: {str(e)}")
    return None

def get_playlist_videos(playlist_id):
    """Get list of video URLs from playlist"""
    videos = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cookie': 'CONSENT=YES+1'
        }
        
        # Try playlist page first
        url = f"https://www.youtube.com/playlist?list={playlist_id}"
        print(f"\nTrying to fetch playlist: {url}")
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            videos = analyze_html_response(response.text)
        
        # If no videos found, try the watch page
        if not videos:
            print("\nTrying watch page method...")
            watch_url = f"https://www.youtube.com/watch?v=J43EoSZMLYE&list={playlist_id}"
            response = requests.get(watch_url, headers=headers)
            
            if response.status_code == 200:
                watch_videos = analyze_html_response(response.text)
                for video in watch_videos:
                    if video not in videos:
                        videos.append(video)

        # Show results
        print(f"\nFound {len(videos)} videos in total")
        if videos:
            print("\nVideos found:")
            for i, video in enumerate(videos, 1):
                print(f"{i}. {url}")
        else:
            print("\nNo videos found. Please check if the playlist is:")
            print("1. Public (not private or unlisted)")
            print("2. Contains videos")
            print("3. Accessible in your region")
            print("\nYou can verify by opening the playlist URL in your browser:")
            print(url)
        
        return videos

    except Exception as e:
        print(f"Error getting playlist videos: {str(e)}")
        return videos

def analyze_html_response(html_content):
    """Analyze HTML content for video links and playlist data"""
    print("\nAnalyzing HTML response...")
    soup = BeautifulSoup(html_content, 'html.parser')
    video_links = []
    
    # Look for ytInitialData in script tags
    print("\nLooking for ytInitialData...")
    for script in soup.find_all('script'):
        if script.string and 'var ytInitialData = ' in script.string:
            try:
                # Extract the JSON data
                data_text = script.string.split('var ytInitialData = ')[1].split(';</script>')[0]
                data = json.loads(data_text)
                
                # Try to find playlist videos in different possible locations
                try:
                    # For playlist page
                    contents = data.get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs', [])[0].get('tabRenderer', {}).get('content', {}).get('sectionListRenderer', {}).get('contents', [])[0].get('itemSectionRenderer', {}).get('contents', [])[0].get('playlistVideoListRenderer', {}).get('contents', [])
                    if contents:
                        for item in contents:
                            if 'playlistVideoRenderer' in item:
                                video_id = item['playlistVideoRenderer'].get('videoId')
                                if video_id:
                                    url = f"https://www.youtube.com/watch?v={video_id}"
                                    if url not in video_links:
                                        video_links.append(url)
                                        print(f"Found video from playlist page: {url}")
                except:
                    pass
                
                try:
                    # For watch page with playlist
                    playlist_panel = data.get('contents', {}).get('twoColumnWatchNextResults', {}).get('playlist', {}).get('playlist', {}).get('contents', [])
                    if playlist_panel:
                        for item in playlist_panel:
                            if 'playlistPanelVideoRenderer' in item:
                                video_id = item['playlistPanelVideoRenderer'].get('videoId')
                                if video_id:
                                    url = f"https://www.youtube.com/watch?v={video_id}"
                                    if url not in video_links:
                                        video_links.append(url)
                                        print(f"Found video from watch page playlist: {url}")
                except:
                    pass
                
            except Exception as e:
                print(f"Error parsing ytInitialData: {str(e)}")
                continue
    
    # If no videos found through ytInitialData, try fallback methods
    if not video_links:
        print("\nTrying fallback methods...")
        
        # Look for video renderers
        renderers = soup.find_all(['ytd-playlist-video-renderer', 'ytd-playlist-panel-video-renderer'])
        for renderer in renderers:
            video_id = renderer.get('data-video-id')
            if video_id:
                url = f"https://www.youtube.com/watch?v={video_id}"
                if url not in video_links:
                    video_links.append(url)
                    print(f"Found video from renderer: {url}")
        
        # Look for thumbnail links
        thumbnails = soup.find_all('a', {'id': 'thumbnail'})
        for thumbnail in thumbnails:
            href = thumbnail.get('href', '')
            if '/watch?v=' in href:
                video_id = href.split('watch?v=')[1].split('&')[0]
                url = f"https://www.youtube.com/watch?v={video_id}"
                if url not in video_links:
                    video_links.append(url)
                    print(f"Found video from thumbnail: {url}")
    
    # Print summary
    if video_links:
        print(f"\nFound {len(video_links)} unique video links:")
        for i, url in enumerate(video_links, 1):
            print(f"{i}. {url}")
    else:
        print("\nNo video links found!")
    
    return video_links

def process_playlist():
    """Process a YouTube playlist"""
    try:
        # Get playlist URL
        print("\nPlease enter the YouTube playlist URL (or 'q' to quit):")
        print("(e.g., https://www.youtube.com/playlist?list=PLAYLIST_ID)")
        print("(or a video URL with a playlist, e.g., https://www.youtube.com/watch?v=VIDEO_ID&list=PLAYLIST_ID)")
        playlist_url = input("> ").strip()
        
        if playlist_url.lower() in ['q', 'quit', 'exit']:
            return False
        
        if not playlist_url:
            print("No URL provided. Please try again or enter 'q' to quit.")
            return True
        
        # Get playlist ID
        playlist_id = get_playlist_id(playlist_url)
        if not playlist_id:
            print("Error: Could not extract playlist ID from URL")
            return True
        
        # Get channel and playlist names
        channel_name, playlist_name = get_channel_and_playlist_info(playlist_id)
        
        # Create safe directory names
        safe_channel_name = get_safe_filename(channel_name)
        safe_playlist_name = get_safe_filename(playlist_name)
        
        # Create directory structure
        channel_dir = safe_channel_name
        if not os.path.exists(channel_dir):
            os.makedirs(channel_dir)
        
        output_dir = os.path.join(channel_dir, safe_playlist_name)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        print(f"\nChannel: {channel_name}")
        print(f"Playlist: {playlist_name}")
        print(f"Getting videos from playlist: {playlist_url}")
        videos = get_playlist_videos(playlist_id)
        
        if not videos:
            print("No videos found in the playlist.")
            return True
        
        print(f"\nFound {len(videos)} videos. Starting transcript download...")
        
        successful = 0
        failed = 0
        
        for i, video_url in enumerate(videos, 1):
            print(f"\nProcessing video {i}/{len(videos)}")
            if download_video_transcript(video_url, output_dir):
                successful += 1
            else:
                failed += 1
            time.sleep(1)  # Add delay to avoid rate limiting
        
        print(f"\nDownload complete!")
        print(f"Successfully downloaded: {successful} transcripts")
        print(f"Failed to download: {failed} transcripts")
        print(f"Transcripts are saved in: {output_dir}")
        return True

    except Exception as e:
        print(f"\nAn unexpected error occurred: {str(e)}")
        print("Please try again with a different playlist URL.")
        return True

def get_channel_and_playlist_info(playlist_id):
    """Get channel name and playlist title"""
    try:
        url = f"https://www.youtube.com/playlist?list={playlist_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to get channel name and playlist title from ytInitialData
            for script in soup.find_all('script'):
                if script.string and 'var ytInitialData = ' in script.string:
                    data_text = script.string
                    start_idx = data_text.find('var ytInitialData = ') + len('var ytInitialData = ')
                    end_idx = data_text.find(';</script>', start_idx)
                    
                    if start_idx > 0 and end_idx > 0:
                        try:
                            data = json.loads(data_text[start_idx:end_idx])
                            
                            # Try to get playlist title
                            playlist_title = None
                            header = data.get('header', {}).get('playlistHeaderRenderer', {})
                            if header:
                                title_obj = header.get('title', {})
                                if 'runs' in title_obj:
                                    playlist_title = ' '.join(t.get('text', '') for t in title_obj['runs'])
                                elif 'simpleText' in title_obj:
                                    playlist_title = title_obj['simpleText']
                            
                            # Try to get channel name
                            channel_name = None
                            owner = header.get('ownerText', {})
                            if 'runs' in owner:
                                channel_name = owner['runs'][0].get('text', '')
                            
                            if channel_name and playlist_title:
                                return channel_name, playlist_title
                            
                        except json.JSONDecodeError:
                            pass
            
            # Fallback to HTML parsing
            # Try to get playlist title
            title_tag = soup.find('meta', {'property': 'og:title'})
            playlist_title = title_tag['content'].replace(' - YouTube', '') if title_tag else f"Playlist_{playlist_id}"
            
            # Try to get channel name
            channel_tag = soup.find('link', {'itemprop': 'name'})
            channel_name = channel_tag['content'] if channel_tag else "Unknown_Channel"
            
            return channel_name, playlist_title
            
    except Exception as e:
        print(f"Error getting channel and playlist info: {str(e)}")
    
    return "Unknown_Channel", f"Playlist_{playlist_id}"

if __name__ == "__main__":
    print("YouTube Playlist Transcript Downloader")
    print("=====================================")
    
    while True:
        try:
            if not process_playlist():
                break
            
            while True:
                print("\nWould you like to process another playlist? (yes/no)")
                response = input("> ").strip().lower()
                
                # Check if the response is actually a playlist URL
                if 'youtube.com/' in response and 'list=' in response:
                    playlist_url = response
                    break
                elif response in ['y', 'yes']:
                    break
                elif response in ['n', 'no', 'q', 'quit', 'exit']:
                    print("Goodbye!")
                    exit(0)
                else:
                    print("Please enter 'yes' or 'no' (or enter a YouTube playlist URL directly)")
                    
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nAn error occurred: {str(e)}")
            print("Please try again or enter 'q' to quit.") 