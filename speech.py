"""Google Cloud Speech API using microphone.

NOTE: It requires dependencies below:
    `pyaudio`
    `google-cloud-speech`

to install:
    pip install pyaudio google-cloud-speech
"""

from __future__ import division

import re
import sys
from google.cloud import speech

import pyaudio
from six.moves import queue

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms each chunk


class MicrophoneStream(object):
    """Opens a recording stream as a generator yielding the audio chunks."""

    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data using queue
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,  #: encoding 16bit
            channels=1,  # audio_channel_count
            rate=self._rate,  # sample_rate_hertz
            input=True,  # whether this is an input stream.
            frames_per_buffer=self._chunk,  # the number of frames per buffer.
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

        self.closed = False

        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b"".join(data)


def listen_print_loop(responses):
    """Iterates through server responses and prints them.

    The responses passed is a generator that will block until a response
    is provided by the server.

    Each response may contain multiple results, and each result may contain
    multiple alternatives; for details, see https://goo.gl/tjCPAU.
    results { alternatives { transcript: "to be or not to be" confidence: 0.92 } alternatives { transcript: "to bee or not to bee" } is_final: true }
    Here we print only the transcription for the top alternative of the top result.

    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.
    """
    num_chars_printed = 0
    for response in responses:
        if not response.results:
            continue

        # The `results` list is consecutive. For streaming, we only care about
        # the first result being considered, since once it's `is_final`, it
        # moves on to considering the next utterance.
        result = response.results[0]
        if not result.alternatives:
            continue

        # Display the transcription of the top alternative.
        transcript = result.alternatives[0].transcript

        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.
        #
        # If the previous result was longer than this one, we need to print
        # some extra spaces to overwrite the previous result
        overwrite_chars = " " * (num_chars_printed - len(transcript))

        if not result.is_final:
            sys.stdout.write(transcript + overwrite_chars + "\r")
            sys.stdout.flush()

            num_chars_printed = len(transcript)

        else:
            print(transcript + overwrite_chars)


            # in case I need time offsets for the words spoken
            # for word_info in result.alternatives[0].words:
            # word = word_info.word
            # start_time = word_info.start_time
            # end_time = word_info.end_time

            # print(
            #     f"Word: {word}, start_time: {start_time.total_seconds()}, end_time: {end_time.total_seconds()}"
            # )


            with open(r"text/transcripts.txt", "a+") as transcript_file:
                transcript_file.write(transcript + overwrite_chars + "\n")
            
            # Exit recognition if any of the transcribed phrases could be
            # one of our keywords.
            if re.search(r"\b(exit|quit)\b", transcript, re.I):
                print("Exiting..")
                break

            num_chars_printed = 0


def main():
    # See http://g.co/cloud/speech/docs/languages
    # for a list of supported languages.
    language_code = "ja-JP"  # a BCP-47 language tag

    client = speech.SpeechClient.from_service_account_file(
        "/home/beki/Desktop/speech/key.json"
    )
    # export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/cloud-speech-86c392d1c134.json"
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=language_code,
        
        # using enhanced model
        # doc: https://googleapis.dev/python/speech/latest/speech_v1/types.html?highlight=enhanced#google.cloud.speech_v1.types.RecognitionConfig.use_enhanced
        # price: 0.024 a min when use_enhanced = False
        # price: 0.036 a min when use_enhanced = True
        # use_enhanced=True,
        # model: 'phone_call', # model should be eitheer `phone_call` or `video`


        # if transcripts need to have time offsets
        # enable_word_time_offsets=True,

    )   

    streaming_config = speech.StreamingRecognitionConfig(
        config=config, interim_results=True
    )

    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        requests = (
            speech.StreamingRecognizeRequest(audio_content=content)
            for content in audio_generator
        )

        responses = client.streaming_recognize(streaming_config, requests)

        # Now, put the transcription responses to use.
        listen_print_loop(responses)


if __name__ == "__main__":
    main()
# [END speech_transcribe_streaming_mic]
