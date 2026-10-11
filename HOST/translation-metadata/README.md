---
language: 
- zh
- en

tags:
- translation

license: cc-by-4.0
---

### zho-eng

## Table of Contents
- [Model Details](#model-details)
- [Uses](#uses)
- [Risks, Limitations and Biases](#risks-limitations-and-biases)
- [Training](#training)
- [Evaluation](#evaluation)
- [Citation Information](#citation-information)
- [How to Get Started With the Model](#how-to-get-started-with-the-model)

## Model Details
- **Model Description:**
- **Developed by:** Language Technology Research Group at the University of Helsinki
- **Model Type:** Translation
- **Language(s):**  
  - Source Language:  Chinese
  - Target Language: English
- **License:** CC-BY-4.0
- **Resources for more information:**
  - [GitHub Repo](https://github.com/Helsinki-NLP/OPUS-MT-train)


## Uses

#### Direct Use

This model can be used for translation and text-to-text generation.


## Risks, Limitations and Biases

**CONTENT WARNING: Readers should be aware this section contains content that is disturbing, offensive, and can propagate historical and current stereotypes.**

Significant research has explored bias and fairness issues with language models (see, e.g., [Sheng et al. (2021)](https://aclanthology.org/2021.acl-long.330.pdf) and [Bender et al. (2021)](https://dl.acm.org/doi/pdf/10.1145/3442188.3445922)).

Further details about the dataset for this model can be found in the OPUS readme: [zho-eng](https://github.com/Helsinki-NLP/Tatoeba-Challenge/tree/master/models/zho-eng/README.md)

## Training

#### System Information 
* helsinki_git_sha: 480fcbe0ee1bf4774bcbe6226ad9f58e63f6c535
* transformers_git_sha: 2207e5d8cb224e954a7cba69fa4ac2309e9ff30b
* port_machine: brutasse
* port_time: 2020-08-21-14:41
* src_multilingual: False
* tgt_multilingual: False

#### Training Data
##### Preprocessing
* pre-processing: normalization + SentencePiece (spm32k,spm32k)
* ref_len: 82826.0
* dataset: [opus](https://github.com/Helsinki-NLP/Opus-MT)
* download original weights: [opus-2020-07-17.zip](https://object.pouta.csc.fi/Tatoeba-MT-models/zho-eng/opus-2020-07-17.zip)

* test set translations: [opus-2020-07-17.test.txt](https://object.pouta.csc.fi/Tatoeba-MT-models/zho-eng/opus-2020-07-17.test.txt)


## Evaluation

#### Results

* test set scores: [opus-2020-07-17.eval.txt](https://object.pouta.csc.fi/Tatoeba-MT-models/zho-eng/opus-2020-07-17.eval.txt)

* brevity_penalty: 0.948


## Benchmarks

| testset               | BLEU  | chr-F |
|-----------------------|-------|-------|
| Tatoeba-test.zho.eng 	| 36.1 	| 0.548 |

## Citation Information

```bibtex
@InProceedings{TiedemannThottingal:EAMT2020,
  author = {J{\"o}rg Tiedemann and Santhosh Thottingal},
  title = {{OPUS-MT} — {B}uilding open translation services for the {W}orld},
  booktitle = {Proceedings of the 22nd Annual Conferenec of the European Association for Machine Translation (EAMT)},
  year = {2020},
  address = {Lisbon, Portugal}
 }
```

## How to Get Started With the Model

```python
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

tokenizer = AutoTokenizer.from_pretrained("Helsinki-NLP/opus-mt-zh-en")

model = AutoModelForSeq2SeqLM.from_pretrained("Helsinki-NLP/opus-mt-zh-en")
```


