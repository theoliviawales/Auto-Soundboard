import speech_recognition as sr
import base64
import json
import config
import sys
import winsound
from pydub import AudioSegment
from os import path
from urllib.parse import urlencode
from urllib.request import Request, HTTPError, URLError, urlopen
from django.shortcuts import render
from django.http import HttpResponse
from django.conf import settings
from .models import SoundboardFile

# With help from "https://stackoverflow.com/questions/36458214/split-speech-audio-file-on-words-in-python"
def extracted_from_sr_recognize_ibm(audio_data, username="IBM_USERNAME", password="IBM_PASSWORD", language="en-US", show_all=False, timestamps=True,
                                word_confidence=True, word_alternatives_threshold=0.1):
    assert isinstance(username, str), "``username`` must be a string"
    assert isinstance(password, str), "``password`` must be a string"

    flac_data = audio_data.get_flac_data(
        convert_rate=None if audio_data.sample_rate >= 16000 else 16000,  # audio samples should be at least 16 kHz
        convert_width=None if audio_data.sample_width >= 2 else 2  # audio samples should be at least 16-bit
    )
    url = "https://stream.watsonplatform.net/speech-to-text/api/v1/recognize?timestamps=true"
    request = Request(url, data=flac_data, headers={
        "Content-Type": "audio/x-flac",
        "X-Watson-Learning-Opt-Out": "true",  # prevent requests from being logged, for improved privacy
    })
    authorization_value = base64.standard_b64encode("{}:{}".format(username, password).encode("utf-8")).decode("utf-8")
    request.add_header("Authorization", "Basic {}".format(authorization_value))

    try:
        response = urlopen(request, timeout=None)
    except HTTPError as e:
        raise sr.RequestError("recognition request failed: {}".format(e.reason))
    except URLError as e:
        raise sr.RequestError("recognition connection failed: {}".format(e.reason))
    response_text = response.read().decode("utf-8")
    result = json.loads(response_text)

    # return results
    if show_all: return result
    if "results" not in result or len(result["results"]) < 1 or "alternatives" not in result["results"][0]:
        raise Exception("Unknown Value Exception")

    transcription = []
    for utterance in result["results"]:
        if "alternatives" not in utterance:
            raise Exception("Unknown Value Exception. No Alternatives returned")
        for hypothesis in utterance["alternatives"]:
            if "transcript" in hypothesis:
                print(hypothesis['timestamps'])
                transcription.append(hypothesis["transcript"])
    return "\n".join(transcription),hypothesis['timestamps']

def index(request):
    if not request.session.session_key:
        request.session.save()
    print(request.session.session_key)
    if request.method == 'POST' and request.FILES['myfile']:
        AUDIO_FILE = request.FILES['myfile']

        r = sr.Recognizer()
        with sr.AudioFile(AUDIO_FILE) as source:
            audio = r.record(source)  # read the entire audio file

        try:
            transcript,timestamps = extracted_from_sr_recognize_ibm(audio, username=settings.IBM_USERNAME, password=settings.IBM_PASSWORD)
        except sr.UnknownValueError:
            print("IBM Speech to Text could not understand audio")
        except sr.RequestError as e:
            print("Could not request results from IBM Speech to Text service; {0}".format(e))

        sound = AudioSegment.from_wav(AUDIO_FILE)

        seen_words = {}

        for utterance in timestamps:
            word,start,end = utterance
            if word not in seen_words or len(seen_words[word]) < (float(end) - float(start)):
                seen_words[word] = sound[float(start) * 1000 : float(end) * 1000]

        return render(request, 'autosounds/index.html', {'unique_words': seen_words})

    return render(request, 'autosounds/index.html', {})
