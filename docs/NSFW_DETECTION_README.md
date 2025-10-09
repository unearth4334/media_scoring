---
tags:
- image-classification
- timm
library_name: timm
license: apache-2.0
---
# Model card for nsfw-image-detection-384

__NOTE: Like all models, this one can make mistakes. NSFW content can be subjective and contextual, this model is intended to help identify this content, use at your own risk.__

`Marqo/nsfw-image-detection-384` is a lightweight image classification model designed to identify NSFW images. The model is approximately 18–20x smaller than other open-source models and achieves a superior accuracy of 98.56% on our dataset. This model uses 384x384 pixel images for the input with 16x16 pixel patches.

This model was trained on a proprietary dataset of 220,000 images. The training set includes 100,000 NSFW examples and 100,000 SFW examples, while the test set contains 10,000 NSFW examples and 10,000 SFW examples. This dataset features a diverse range of content, including: real photos, drawings, Rule 34 material, memes, and AI-generated images. The definition of NSFW can vary and is sometimes contextual, our dataset was constructed to contain challenging examples however this definition may not be 100% aligned with every use case, as such we recommend experimenting and trying different thresholds to determine if this model is suitable for your needs.

## Model Usage

### Image Classification with timm

```bash
pip install timm
```

```python
from urllib.request import urlopen
from PIL import Image
import timm
import torch

img = Image.open(urlopen(
    'https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/beignets-task-guide.png'
))

model = timm.create_model("hf_hub:Marqo/nsfw-image-detection-384", pretrained=True)
model = model.eval()

data_config = timm.data.resolve_model_data_config(model)
transforms = timm.data.create_transform(**data_config, is_training=False)

with torch.no_grad():
    output = model(transforms(img).unsqueeze(0)).softmax(dim=-1).cpu()

class_names = model.pretrained_cfg["label_names"]
print("Probabilities:", output[0])
print("Class:", class_names[output[0].argmax()])
```

## Evaluation

This model outperforms existing NSFW detectors on our dataset, here we provide an evaluation against [AdamCodd/vit-base-nsfw-detector](https://huggingface.co/AdamCodd/vit-base-nsfw-detector) and [Falconsai/nsfw_image_detection](https://huggingface.co/Falconsai/nsfw_image_detection):

![Evaluation against other models](./images/Comparison.png)

### Thresholds and Precision vs Recall

Adjusting the threshold for the NSFW probability can let you trade off precision, recall, and accuracy. This maybe be useful in different applications where different degrees of confidence are required.

![Thresholded Evaluation](./images/ThresholdEvals.png)
![Precision and Recall Curves](./images/PrecisionRecallCurves.png)

## Training Details

This model is a finetune of the [timm/vit_tiny_patch16_384.augreg_in21k_ft_in1k](https://huggingface.co/timm/vit_tiny_patch16_384.augreg_in21k_ft_in1k) model.

### Args

```yml
batch_size: 256
color_jitter: 0.2
color_jitter_prob: 0.05
cutmix: 0.1
drop: 0.1
drop_path: 0.05
epoch_repeats: 0.0
epochs: 20
gaussian_blur_prob: 0.005
hflip: 0.5
lr: 5.0e-05
mixup: 0.1
mixup_mode: batch
mixup_prob: 1.0
mixup_switch_prob: 0.5
momentum: 0.9
num_classes: 2
opt: adamw
remode: pixel
reprob: 0.5
sched: cosine
smoothing: 0.1
warmup_epochs: 2
warmup_lr: 1.0e-05
warmup_prefix: false
```


## Citation

```
@article{dosovitskiy2020vit,
  title={An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale},
  author={Dosovitskiy, Alexey and Beyer, Lucas and Kolesnikov, Alexander and Weissenborn, Dirk and Zhai, Xiaohua and Unterthiner, Thomas and  Dehghani, Mostafa and Minderer, Matthias and Heigold, Georg and Gelly, Sylvain and Uszkoreit, Jakob and Houlsby, Neil},
  journal={ICLR},
  year={2021}
}
```


```
@misc{rw2019timm,
  author = {Ross Wightman},
  title = {PyTorch Image Models},
  year = {2019},
  publisher = {GitHub},
  journal = {GitHub repository},
  doi = {10.5281/zenodo.4414861},
  howpublished = {\url{https://github.com/huggingface/pytorch-image-models}}
}
```