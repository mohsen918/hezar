"""
A DistilBERT model for text classification built using HuggingFace Transformers
"""
from typing import Dict

from torch import nn
from transformers import DistilBertConfig, DistilBertModel

from ....models import Model
from ....registry import register_model
from .distilbert_text_classification_config import DistilBertTextClassificationConfig


@register_model(model_name="distilbert_text_classification", config_class=DistilBertTextClassificationConfig)
class DistilBertTextClassification(Model):
    """
    A standard 🤗Transformers DistilBert model for text classification

    Args:
        config: The whole model config including arguments needed for the inner 🤗Transformers model.
    """

    def __init__(self, config: DistilBertTextClassificationConfig, **kwargs):
        super().__init__(config, **kwargs)
        self.distilbert = DistilBertModel(self._build_inner_config())
        self.pre_classifier = nn.Linear(self.config.dim, self.config.dim)
        self.classifier = nn.Linear(self.config.dim, self.config.num_labels)
        self.dropout = nn.Dropout(self.config.seq_classif_dropout)

    def _build_inner_config(self):
        if self.config.num_labels is None and self.config.id2label is None:
            raise ValueError("Both `num_labels` and `id2label` are None. Please provide at least one of them!")
        if self.config.id2label and self.config.num_labels is None:
            self.config.num_labels = len(self.config.id2label)
        bert_config = DistilBertConfig(**self.config)
        return bert_config

    def forward(self, inputs, **kwargs) -> Dict:
        input_ids = inputs["token_ids"]
        attention_mask = inputs["attention_mask"]
        token_type_ids = inputs["token_type_ids"]
        position_ids = inputs["position_ids"]
        head_mask = inputs["head_mask"]
        inputs_embeds = inputs["inputs_embeds"]
        output_attentions = inputs["output_attentions"]
        output_hidden_states = inputs["output_hidden_states"]

        lm_outputs = self.distilbert(
            input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            position_ids=position_ids,
            head_mask=head_mask,
            inputs_embeds=inputs_embeds,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            **kwargs,
        )
        hidden_state = lm_outputs[0]
        pooled_output = hidden_state[:, 0]
        pooled_output = self.pre_classifier(pooled_output)
        pooled_output = nn.ReLU()(pooled_output)
        pooled_output = self.dropout(pooled_output)
        logits = self.classifier(pooled_output)

        outputs = {
            "logits": logits,
            "hidden_states": lm_outputs.hidden_states,
            "attentions": lm_outputs.attentions,
        }
        return outputs

    def post_process(self, inputs, **kwargs) -> Dict:
        logits = inputs["logits"]
        predictions = logits.argmax(1)
        predictions_probs = logits.softmax(1).max(1)
        outputs = {"labels": [], "probs": []}
        for prediction, prob in zip(predictions, predictions_probs):
            label = self.config.id2label[prediction.item()]
            outputs["labels"].append(label)
            outputs["probs"].append(prob.item())
        return outputs
