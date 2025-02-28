from youtube_transcript_api import YouTubeTranscriptApi
import re
from urllib.parse import urlparse, parse_qs
import requests
import os
import time
from bs4 import BeautifulSoup
import json

def get_playlist_id(url):
    """Extract playlist ID from YouTube URL"""
    try:
        parsed_url = urlparse(url)
        if 'list=' in url:
            return parse_qs(parsed_url.query)['list'][0]
    except Exception as e:
        print(f"Error extracting playlist ID: {str(e)}")
    return None

def analyze_html_response(html_content):
    """Analyze HTML content for video links and playlist data"""
    print("\nAnalyzing HTML response...")
    soup = BeautifulSoup(html_content, 'html.parser')
    video_links = []
    
    # Save the HTML for debugging
    with open("playlist_page.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("\nSaved HTML page to playlist_page.html for debugging")
    
    # First try: Direct link extraction from thumbnails
    print("\nLooking for thumbnail links...")
    thumbnail_links = soup.find_all('a', {'id': 'thumbnail', 'class': 'yt-simple-endpoint inline-block style-scope ytd-thumbnail'})
    if thumbnail_links:
        print(f"Found {len(thumbnail_links)} thumbnail links")
        for link in thumbnail_links:
            href = link.get('href', '')
            if '/watch?v=' in href:
                video_id = href.split('watch?v=')[1].split('&')[0]
                url = f"https://www.youtube.com/watch?v={video_id}"
                if url not in video_links:
                    video_links.append(url)
                    print(f"Found video link: {url}")
    
    # Second try: Look for video renderers
    print("\nLooking for video renderers...")
    renderers = soup.find_all(['ytd-playlist-video-renderer', 'ytd-playlist-panel-video-renderer'])
    if renderers:
        print(f"Found {len(renderers)} video renderers")
        for renderer in renderers:
            # Try to get video ID from the renderer's attributes
            video_id = renderer.get('data-video-id')
            if video_id:
                url = f"https://www.youtube.com/watch?v={video_id}"
                if url not in video_links:
                    video_links.append(url)
                    print(f"Found video from renderer data: {url}")
                continue
            
            # Look for thumbnail links within the renderer
            thumbnail = renderer.find('a', {'id': 'thumbnail'})
            if thumbnail and 'href' in thumbnail.attrs:
                href = thumbnail['href']
                if '/watch?v=' in href:
                    video_id = href.split('watch?v=')[1].split('&')[0]
                    url = f"https://www.youtube.com/watch?v={video_id}"
                    if url not in video_links:
                        video_links.append(url)
                        print(f"Found video from renderer thumbnail: {url}")
    
    # Third try: Look for any watch links
    print("\nLooking for watch links...")
    all_links = soup.find_all('a', href=True)
    for link in all_links:
        href = link.get('href', '')
        if '/watch?v=' in href:
            video_id = href.split('watch?v=')[1].split('&')[0]
            url = f"https://www.youtube.com/watch?v={video_id}"
            if url not in video_links:
                video_links.append(url)
                print(f"Found watch link: {url}")
    
    # Fourth try: Look for video IDs in any script tags
    print("\nLooking for video IDs in scripts...")
    scripts = soup.find_all('script')
    for script in scripts:
        if not script.string:
            continue
        
        # Look for videoId patterns
        matches = re.findall(r'"videoId":"([^"]+)"', script.string)
        for video_id in matches:
            url = f"https://www.youtube.com/watch?v={video_id}"
            if url not in video_links:
                video_links.append(url)
                print(f"Found video ID in script: {url}")
    
    # Print summary
    if video_links:
        print(f"\nFound {len(video_links)} unique video links:")
        for i, url in enumerate(video_links, 1):
            print(f"{i}. {url}")
    else:
        print("\nNo video links found!")
        print("Debug files have been created:")
        print("1. playlist_page.html - The raw HTML page")
        print("Please check if the playlist is accessible and contains videos.")
    
    return video_links

def get_playlist_videos(playlist_id, original_url=None):
    """Get list of video URLs from playlist"""
    videos = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cookie': 'CONSENT=YES+1'
        }
        
        # If we have a watch URL, try that first
        if original_url and 'watch?v=' in original_url:
            print(f"\nTrying to fetch from watch URL: {original_url}")
            response = requests.get(original_url, headers=headers)
            if response.status_code == 200:
                videos = analyze_html_response(response.text)
        
        # If no videos found yet, try the playlist page
        if not videos:
            url = f"https://www.youtube.com/playlist?list={playlist_id}"
            print(f"\nTrying to fetch playlist: {url}")
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                videos = analyze_html_response(response.text)

        # Show results
        print(f"\nFound {len(videos)} videos in total")
        if videos:
            print("\nVideos found:")
            for i, video in enumerate(videos, 1):
                print(f"{i}. {video}")
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

def get_safe_filename(title):
    """Convert title to safe filename"""
    safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
    safe_title = safe_title.replace(' ', '_')
    return safe_title

def get_video_title(video_id):
    """Get video title using YouTube's oEmbed API"""
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        response = requests.get(oembed_url)
        if response.status_code == 200:
            return response.json()['title']
    except Exception:
        pass
    return video_id

def get_transcript(video_id):
    """Try to get transcript in English first, then fall back to original language"""
    try:
        # Get all available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        print("\nAvailable transcript languages:")
        for transcript in transcript_list:
            print(f"- {transcript.language} ({'Auto-generated' if transcript.is_generated else 'Manual'})")
        
        # First priority: Manual English transcript
        try:
            transcript = transcript_list.find_transcript(['en'])
            if not transcript.is_generated:
                print("\nUsing manual English transcript")
                return transcript.fetch()
        except:
            pass

        # Second priority: Auto-generated English transcript
        try:
            transcript = transcript_list.find_generated_transcript(['en'])
            print("\nUsing auto-generated English transcript")
            return transcript.fetch()
        except:
            pass
        
        # Third priority: Try to translate to English if available
        try:
            # Get the first manual transcript
            manual_transcripts = [t for t in transcript_list.manual_transcripts]
            if manual_transcripts:
                original_transcript = transcript_list.find_transcript([manual_transcripts[0].language_code])
                try:
                    translated = original_transcript.translate('en')
                    print(f"\nTranslated manual transcript from {original_transcript.language} to English")
                    return translated.fetch()
                except:
                    print(f"\nUsing original manual transcript in {original_transcript.language} (translation not available)")
                    return original_transcript.fetch()
        except:
            pass

        # Fourth priority: First available manual transcript
        try:
            manual_transcripts = [t for t in transcript_list.manual_transcripts]
            if manual_transcripts:
                transcript = transcript_list.find_transcript([manual_transcripts[0].language_code])
                print(f"\nUsing manual transcript in {transcript.language}")
                return transcript.fetch()
        except:
            pass
        
        # Last priority: First available transcript of any kind
        try:
            available = list(transcript_list)
            if available:
                transcript = available[0]
                print(f"\nUsing available transcript in {transcript.language}")
                return transcript.fetch()
        except:
            pass
            
    except Exception as e:
        if "No transcripts were found" in str(e):
            print("\nNo transcripts available for this video")
        else:
            print(f"\nError getting transcript: {str(e)}")
    return None

def download_video_transcript(video_url, output_dir):
    """Download transcript for a single video"""
    try:
        # Get video ID
        if 'watch?v=' in video_url:
            video_id = video_url.split('watch?v=')[1].split('&')[0]
        else:
            print(f"Invalid video URL: {video_url}")
            return False

        # Get video title
        video_title = get_video_title(video_id)
        safe_title = get_safe_filename(video_title)
        print(f"\nProcessing video: {video_title}")

        # Get transcript
        transcript = get_transcript(video_id)
        if not transcript:
            print("Could not get transcript (no captions available in any language)")
            return False

        # Format transcript - now without timestamps
        formatted_transcript = []
        for entry in transcript:
            formatted_transcript.append(entry['text'])

        # Save to file
        filename = os.path.join(output_dir, f"{safe_title}_transcript.txt")
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(formatted_transcript))
        
        print(f"Transcript saved to: {filename}")
        return True

    except Exception as e:
        print(f"Error processing video: {str(e)}")
        return False

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
            
            # Try to get channel name
            channel_name = None
            channel_links = soup.find_all('a', {'class': 'yt-simple-endpoint style-scope yt-formatted-string'})
            for link in channel_links:
                if '@' in link.text or 'channel/' in str(link.get('href', '')):
                    channel_name = link.text.strip()
                    break
            
            # Try to get playlist name
            playlist_name = None
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.text.strip()
                # Remove "- YouTube" from the end if present
                if " - YouTube" in title:
                    title = title.replace(" - YouTube", "")
                playlist_name = title
            
            if channel_name and playlist_name:
                return channel_name, playlist_name
            
    except Exception as e:
        print(f"Error getting channel and playlist info: {str(e)}")
    
    return "Unknown_Channel", f"Playlist_{playlist_id}"

def process_playlist():
    try:
        # Get playlist URL
        print("\nPlease enter the YouTube playlist URL (or 'q' to quit):")
        print("(e.g., https://www.youtube.com/playlist?list=PLAYLIST_ID)")
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
        videos = get_playlist_videos(playlist_id, playlist_url)
        
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