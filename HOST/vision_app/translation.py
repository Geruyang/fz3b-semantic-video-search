"""Host-only offline Chinese prompts; pinned OPUS model, no cloud requests."""
from pathlib import Path
import sys

def chinese(text):return any('\u4e00'<=c<='\u9fff' for c in text)
def model_path():
    if getattr(sys,'frozen',False):return Path(sys.executable).parent/'translation'
    return Path(__file__).resolve().parents[4]/'deliverables/vision-console/FZ3BVisionConsole/translation'

class PromptTranslator:
    def __init__(self):self.model=self.tokenizer=None;self.cache={}
    def translate(self,text):
        if not chinese(text):return text
        examples={'桌面上的杯子':'a photo of a cup on a desk','有人在房间里':'a photo of a person in a room'}
        if text in examples:return examples[text]
        if text in self.cache:return self.cache[text]
        if self.model is None:
            from transformers import MarianMTModel,MarianTokenizer
            location=str(model_path())
            self.tokenizer=MarianTokenizer.from_pretrained(location,local_files_only=True)
            self.model=MarianMTModel.from_pretrained(location,local_files_only=True).eval()
        import torch
        values=self.tokenizer([text],return_tensors='pt',truncation=False)
        if values['input_ids'].shape[1]>256:raise ValueError('中文描述过长，请精简为一句场景描述')
        with torch.inference_mode():result=self.model.generate(**values,max_new_tokens=128,num_beams=4)
        output=self.tokenizer.batch_decode(result,skip_special_tokens=True)[0].strip()
        if not output or chinese(output):raise ValueError('中文翻译失败，请使用“中文标签 | 英文描述”')
        import re
        output=re.sub(r"^there(?: is| are|'s)\s+",'',output.rstrip('.'),flags=re.IGNORECASE)
        output='a photo of '+output if not output.lower().startswith('a photo of') else output
        self.cache[text]=output;return output
    def items(self,items):return [dict(item,translated_text=self.translate(item['text'])) for item in items]

def same_intent(a,b):return [{k:x[k] for k in ('id','label','text')} for x in a]==[{k:x[k] for k in ('id','label','text')} for x in b]
