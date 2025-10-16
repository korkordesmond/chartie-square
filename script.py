import os
import requests
import speech_recognition as sr
import ffmpeg
import tempfile
from pydub import AudioSegment
import wave
import json

# Initialize speech recognizer
recognizer = sr.Recognizer()
MEDIA_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.mp3', '.wav', '.flac', '.m4a', '.aac'}

def extract_audio_from_video(video_path):
    """Extract audio from video file using ffmpeg"""
    try:
        # Create temporary WAV file
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        temp_audio_path = temp_audio.name
        temp_audio.close()
        
        print("Extracting audio from video...")
        # Use ffmpeg to extract audio and convert to WAV
        (
            ffmpeg
            .input(video_path)
            .output(temp_audio_path, ac=1, ar=16000, acodec='pcm_s16le')
            .overwrite_output()
            .run(quiet=True, capture_stdout=True, capture_stderr=True)
        )
        
        return temp_audio_path
    except ffmpeg.Error as e:
        print(f"FFmpeg error: {e.stderr.decode() if e.stderr else 'Unknown error'}")
        return None
    except Exception as e:
        print(f"Error extracting audio from video: {e}")
        return None

def convert_audio_to_wav(audio_path):
    """Convert any audio file to WAV format using pydub"""
    try:
        file_ext = os.path.splitext(audio_path)[1].lower()
        
        # If already WAV, return as is
        if file_ext == '.wav':
            return audio_path
        
        print(f"Converting {file_ext} to WAV...")
        
        # Load audio file based on format
        if file_ext == '.mp3':
            audio = AudioSegment.from_mp3(audio_path)
        elif file_ext == '.flac':
            audio = AudioSegment.from_file(audio_path, "flac")
        elif file_ext == '.m4a':
            audio = AudioSegment.from_file(audio_path, "m4a")
        elif file_ext == '.aac':
            audio = AudioSegment.from_file(audio_path, "aac")
        else:
            # Try generic file loading
            audio = AudioSegment.from_file(audio_path)
        
        # Create temporary WAV file
        temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        temp_wav_path = temp_wav.name
        temp_wav.close()
        
        # Export as WAV with optimized settings for speech recognition
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(temp_wav_path, format="wav")
        return temp_wav_path
        
    except Exception as e:
        print(f"Error converting audio file: {e}")
        return None

def split_audio_file(audio_path, chunk_length_ms=30000):
    """Split large audio file into smaller chunks"""
    try:
        print("Splitting audio file into chunks...")
        audio = AudioSegment.from_wav(audio_path)
        chunks = []
        
        # Split audio into chunks
        for i in range(0, len(audio), chunk_length_ms):
            chunk = audio[i:i + chunk_length_ms]
            chunk_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'_chunk_{i//1000}.wav')
            chunk_path = chunk_file.name
            chunk_file.close()
            chunk.export(chunk_path, format="wav")
            chunks.append(chunk_path)
        
        return chunks
    except Exception as e:
        print(f"Error splitting audio file: {e}")
        return [audio_path]  # Return original file if splitting fails

def transcribe_with_fallback(audio_path):
    """Try multiple speech recognition services with fallbacks"""
    transcription = ""
    
    #Google Speech Recognition
    try:
        print("Trying Google Speech Recognition...")
        with sr.AudioFile(audio_path) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
            print("✓ Google Speech Recognition successful")
            return text
    except Exception as e:
        print(f"Google Speech Recognition failed: {e}")
    
    #Then, Google Cloud Speech
    try:
        print("Trying Google Cloud Speech...")
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)
            # You would need to set up GOOGLE_APPLICATION_CREDENTIALS for this
            text = recognizer.recognize_google_cloud(audio_data)
            print("✓ Google Cloud Speech successful")
            return text
    except Exception as e:
        print(f"Google Cloud Speech failed: {e}")
    

def transcribe_audio_file(audio_path):
    """Transcribe audio file with chunking and multiple fallbacks"""
    try:
        # Check file size and split if necessary
        file_size = os.path.getsize(audio_path)
        max_size = 10 * 1024 * 1024  # 10MB limit for Google Speech Recognition
        
        if file_size > max_size:
            print("File too large, splitting into chunks...")
            chunks = split_audio_file(audio_path)
            full_transcription = ""
            
            for i, chunk_path in enumerate(chunks):
                print(f"Transcribing chunk {i+1}/{len(chunks)}...")
                chunk_text = transcribe_with_fallback(chunk_path)
                full_transcription += " " + chunk_text
                
                # Clean up chunk file
                if chunk_path != audio_path:
                    os.unlink(chunk_path)
            
            return full_transcription.strip()
        else:
            return transcribe_with_fallback(audio_path)
            
    except Exception as e:
        print(f"Error during transcription: {e}")
        return ""

def transcribe_media_file(filename):
    """Transcribe media file (video or audio)"""
    file_ext = os.path.splitext(filename)[1].lower()
    
    # Handle video files
    video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv'}
    if file_ext in video_extensions:
        temp_audio_path = extract_audio_from_video(filename)
        if not temp_audio_path:
            return ""
        
        try:
            transcription = transcribe_audio_file(temp_audio_path)
            return transcription
        finally:
            # Clean up temporary audio file
            if os.path.exists(temp_audio_path):
                os.unlink(temp_audio_path)
    
    # Handle audio files
    else:
        wav_path = convert_audio_to_wav(filename)
        if not wav_path:
            return ""
        
        try:
            transcription = transcribe_audio_file(wav_path)
            return transcription
        finally:
            # Clean up temporary WAV file if it was created
            if wav_path != filename and os.path.exists(wav_path):
                os.unlink(wav_path)

# Get and transcribe the file
while True:
    filename = input("Enter path to your video/audio file (Add extension): ").strip()
    
    if not os.path.isfile(filename):
        print(f"Error: File '{filename}' not found. Please try again.")
        continue
    
    # Check if file has a media extension
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in MEDIA_EXTENSIONS:
        response = input(f"Warning: '{file_ext}' is not a common media extension. Continue anyway? (y/n): ")
        if response.lower() != 'y':
            continue
    
    break

# Transcribe the file
print(f"Processing file: {filename}")
transcribed_text = transcribe_media_file(filename)

if not transcribed_text:
    print("\n" + "="*50)
    print("TRANSCRIPTION FAILED")
    print("Possible reasons:")
    print("1. Network connection issues")
    print("2. Audio file too long or too large")
    print("3. Poor audio quality")
    print("4. Service limitations")
    print("="*50)
    
    # Provide manual input option
    print("\nSince transcription failed, you can:")
    print("1. Enter the transcription manually")
    print("2. Try again with a different file")
    print("3. Use the Q&A system with custom text")
    
    choice = input("Enter your choice (1/2/3): ").strip()
    
    if choice == "1":
        transcribed_text = input("Paste the transcription text here: ").strip()
    elif choice == "2":
        print("Please restart the script with a different file.")
        exit()
    elif choice == "3":
        transcribed_text = "No transcription available. Please ask general questions."
    else:
        print("Invalid choice. Exiting.")
        exit()

# Format the transcription
if transcribed_text:
    sentences = transcribed_text.split('.')
    transcription = '\n'.join([(f"{i+1}. {t.strip()}") for i,t in enumerate(sentences) if t.strip()])
    print(f"\nThis is the transcription of your file, {filename}.\n\n{transcription}\n")

    # Q&A loop with the transcription as context
    print("\n" + "="*50)
    print("You can now ask questions about the transcription!")
    print("Type 'quit' to exit.")
    print("="*50)

    while True:
        try:
            user_input = input('\nYou: ').strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("Goodbye!")
                break
                
            if not user_input:
                continue
            
            # Prepare the message with system prompt and transcription context
            system_prompt = f"""You are a helpful assistant that answers questions based on the following transcription. If a statement is entered you can give answers whether it is true or false base on transcript or your own research. 
            If the answer cannot be found in the transcription, say "I cannot find that information in the transcription, but based on what i know", then answer the question
            
            Transcription:
            {transcription}
            
            Question: {user_input}
            Answer:"""
            
            data = {'message': system_prompt}
            
            # Make sure to send proper JSON with correct headers
            headers = {'Content-Type': 'application/json'}
            response = requests.post('http://127.0.0.1:8000/api/v1/chat/', json=data, headers=headers)
            
            if response.status_code == 200:
                response_data = response.json()
                # Handle different response formats
                if isinstance(response_data, dict):
                    if 'response' in response_data:
                        print(f"\nAgent: {response_data['response']}")
                    elif 'error' in response_data:
                        print(f"\nAgent Error: {response_data['error']}")
                    else:
                        print(f"\nAgent: {response_data}")
                else:
                    print(f"\nAgent: {response_data}")
            else:
                print(f"Error: Received status code {response.status_code}")
                print("Response content:", response.text)
                
        except requests.exceptions.ConnectionError:
            print("Error: Cannot connect to server. Please ensure the server is running.")
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")