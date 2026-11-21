import whisper

def transcribe(video_path, model_name='base'):
    model = whisper.load_model(model_name)
    result = model.transcribe(str(video_path), fp16=False, verbose=False)
    return result.get('segments', []), result.get('text', '')
