from io import BytesIO

import requests
import timm
import torch
from PIL import Image
from timm.data import create_transform, resolve_data_config


class CustomImagePipeline:
    def __init__(self, model, transform, labels):
        self.model = model
        self.transform = transform
        self.labels = labels

    def __call__(self, image):
        # Preprocess
        if isinstance(image, str):
            if image.startswith("http://") or image.startswith("https://"):
                response = requests.get(image)
                image = Image.open(BytesIO(response.content)).convert("RGB")
            else:
                image = Image.open(image).convert("RGB")
        elif isinstance(image, Image.Image):
            image = image.convert("RGB")
        else:
            raise ValueError("Unsupported image format")

        inputs = self.transform(image).unsqueeze(0)

        # Forward pass
        with torch.no_grad():
            outputs = self.model(inputs)

        # Postprocess
        probabilities = torch.nn.functional.softmax(outputs[0], dim=0)
        return {label: prob.item() for label, prob in zip(self.labels, probabilities)}


# Load the pretrained model
model = timm.create_model("hf_hub:StephanAkkerman/chart-recognizer", pretrained=True)
model.eval()

# Create transform and get labels
transform = create_transform(**resolve_data_config(model.pretrained_cfg, model=model))
labels = model.pretrained_cfg["label_names"]

# Create the custom pipeline
image_pipeline = CustomImagePipeline(model=model, transform=transform, labels=labels)


def classify_img(image) -> str:
    probabilities = image_pipeline(image)
    # Return the max probability label
    return max(probabilities, key=probabilities.get)
