import queue, sys
import sounddevice as sd
import vosk, json

class Listener:
    def __init__(self, model_path: str, samplerate: int = 16000):
        self.model = vosk.Model(model_path)
        self.samplerate = samplerate
        self.q = queue.Queue()

    def _callback(self, indata, frames, time, status):
        if status:
            print(status, file=sys.stderr)
        self.q.put(bytes(indata))

    def listen_once(self, seconds: int = 5) -> str:
        rec = vosk.KaldiRecognizer(self.model, self.samplerate)
        with sd.RawInputStream(samplerate=self.samplerate, blocksize=8000, dtype='int16', channels=1, callback=self._callback):
            while True:
                data = self.q.get()
                if rec.AcceptWaveform(data):
                    break
        res = json.loads(rec.Result())
        return res.get("text", "")