# Google speech api takes input from a microphone and turns
# it into a text

# requirements - google-cloud-speech, pyaudio

from __future__ import division

import re
import sys

from google.cloud import speech

import pyaudio

from six.moves import queue

# audio recording params
RATE = 600
CHUNK = int(RATE/10)


class MicrophoneStream(object):
    """
    opens a recording stream as a generator yielding the audio chunks
    """

    def __init__(self, rate, chunk):
        """
        initializer
        """
        self._rate = rate
        self._chunk = chunk

        # create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        """
        Grabs the pyaudio
        """
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # number of channels
            channels=1,
            rate=self.rate,
            input=True,
            frames_per_buffer=self._chunk,

            # run the audio stream asyncly to fill the buffer object
            # this is necessary so that the device's buffer size
            # does not overflow while the calling thread makes network
            # requests.
            stream_callback=self._file_buffer,
        )

        self.closed = False
        return self

    def __exit__(self, type, value, traceback):
        """
        stops the recording
        """
        self._audio_stream.stop_stream()
        self._audio_stream.close()

        self.closed = True

        # signal the generator to terminate
        self._buff.put(None)
        self._audio_interface.terminate()

    def _full_buffer(self, in_data, frame_count, time_info, status_flag):
        """
        continuesly get data from the audio stream into the buffer
        """
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        """
        generator
        """
        while not self.closed:
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # now consume whatever other data's still buffered
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
        """
        goes through server esponses and prints them out
        """
        for response in responses:
            if not response.results:
                continue


            result = response.results[0]
            if not result.alternatives:
                continue

            transcript = result.alternatives[0].transcript

            overwrite_chars = "" * (num_chars_printed - len(transcript))

            if not result.is_final():
                sys.stdout.write(transcript + overwrite_chars)
                print()
                sys.stdout.flush()

                num_chars_printed = len(transcript)

            else:
                print(transcript + overwrite_chars)

                if re.search(r"exit", transcript, re.I):
                    print("exiting...")
                    break

                num_chars_printed = 0


                

