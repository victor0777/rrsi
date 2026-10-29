# 논문 읽기 노트

## 3분 요약
This paper introduces the Multimodal Named Entity Recognition (MNER) task to address the challenges of noisy, short user-generated content. The authors propose a Bi-LSTM-CRF model that integrates visual features from InceptionNet with textual data. A key innovation is a modality attention mechanism that dynamically weights word, character, and visual inputs per token. This mechanism helps suppress noise from typos and out-of-vocabulary words by relying on character-level features. The study also releases the SnapCaptions dataset, comprising 10,000 expert-annotated Snapchat image-caption pairs. Visual contexts effectively resolve ambiguities, such as distinguishing between different meanings of a word based on the accompanying image. However, the dataset's specificity to Snapchat captions and the lack of raw images may limit generalizability to other platforms.

_source: Front matter_

### Front Matter Context and Scope

The source material for this section is limited to the paper's title and abstract. Consequently, specific metadata regarding author names, institutional affiliations, and the exact publication venue (conference or journal) is absent from the supplied text. While the execution strategy aims to identify these details to gauge academic standing and potential bias, the current source scope does not contain the necessary information to resolve these questions. Therefore, the following analysis focuses on the core technical claims and task definitions presented in the title and abstract, which serve as the primary context for understanding the paper's scope.

### Task Definition: Multimodal Named Entity Recognition

The paper introduces a new task designated as **Multimodal Named Entity Recognition (MNER)**. This task is specifically tailored for noisy user-generated data, such as tweets or Snapchat captions. The defining characteristic of this data is the combination of short text with accompanying images. The authors highlight that social media posts often feature inconsistent or incomplete syntax and lexical notations, with very limited surrounding textual context. These factors create significant challenges for traditional Named Entity Recognition (NER) systems, which typically rely on rich textual context to identify and classify entities. By introducing MNER, the paper addresses the gap in handling multimodal inputs where visual information is essential for disambiguating or identifying entities that are unclear in the text alone.

### Dataset: SnapCaptions

To support the MNER task, the authors created a new dataset called **SnapCaptions**. This dataset consists of Snapchat image-caption pairs submitted to public and crowd-sourced stories. A key feature of this dataset is that it includes fully annotated named entities. The creation of this dataset is crucial because it provides a standardized benchmark for evaluating models on the specific challenges of noisy, short-form multimodal data. The use of real-world social media data ensures that the dataset reflects the actual noise and variability found in user-generated content, rather than clean, curated academic datasets.

### Model Architecture and Mechanism

The proposed model builds upon state-of-the-art Bi-LSTM word/character-based NER models. It introduces two specific enhancements to handle multimodal inputs:
1.  **Deep Image Network:** This component incorporates relevant visual context to augment textual information. By processing the image, the model can extract visual cues that may clarify ambiguous text.
2.  **Generic Modality-Attention Module:** This module learns to attenuate irrelevant modalities while amplifying the most informative ones. It is adaptive to each sample and token, meaning it dynamically determines whether to rely more on text or image features for specific parts of the input. This mechanism is critical for handling cases where one modality may be noisy or uninformative, allowing the model to focus on the signal most relevant for entity recognition.

### Performance Claims and Applications

The source states that the proposed MNER model with modality attention "significantly outperforms the state-of-the-art text-only NER models." This claim is attributed to the successful leveraging of provided visual contexts. The paper suggests that this performance improvement opens up potential applications for MNER across various social media platforms. However, the source statements provided do not include specific quantitative metrics, benchmark names, or exact numerical values for this performance comparison. Therefore, the claim of "significant outperformance" is noted as a qualitative assertion from the abstract, without the specific data points to verify the magnitude of the improvement.

### Unresolved Dependencies and Missing Metadata

*   **Author Affiliations:** The source statements do not list the authors or their institutional backgrounds. This information is necessary to assess the research group's credibility and potential biases but remains an open dependency.
*   **Publication Venue:** The conference or journal name is not specified in the provided text. Identifying the venue is crucial for determining the paper's academic tier and whether it aligns with top-tier NLP or Multimodal AI standards. This remains an open dependency.
*   **Quantitative Evidence:** While the abstract claims significant outperformance, no specific metrics (e.g., F1 score), baselines, or dataset splits are provided in this scope. The exact values supporting the performance claim are not available in the current source statements.

**One-line summary:** The paper introduces the MNER task and SnapCaptions dataset for noisy social media data, proposing a Bi-LSTM model with modality attention that claims to outperform text-only baselines, though specific author, venue, and quantitative details are absent from this source scope.

_source: 1 Introduction_

### Problem Context and Limitations of Text-Only NER
The paper addresses the challenge of extracting structured information from unstructured social media content, such as free-form text and images. Named Entity Recognition (NER) is identified as a critical step for enabling applications like personalized assistance and recommendations. While previous neural approaches, such as LSTMs with word embeddings and character-level features (e.g., CharLSTM/CNN), have succeeded on well-formed text, they face significant hurdles with the "extremely short and coarse" text typical of social media. Two specific types of noise are highlighted:
1.  **Polysemy due to lack of context:** Short posts often lack sufficient textual context to resolve ambiguous terms. For example, "monopoly" could refer to a board game (a named entity) or an economic concept, making text-only resolution difficult.
2.  **Noisy tokens and misspellings:** Social media text contains many unknown tokens due to inconsistent lexical notations and trending entities. For instance, "Marshmelloooo" is a misspelling of the music producer "Marshmello." Word-embedding-based models are vulnerable to these unknown tokens because they rely on pre-trained vectors that do not cover such variations.

### Definition of the MNER Task
The paper introduces a multimodal approach to address these limitations by leveraging auxiliary modalities, specifically images, alongside text. The task is defined as recognizing named entities in text input by utilizing both image and text data. This is distinct from standard NER, which relies solely on textual context. The rationale is that visual context can provide disambiguation cues that text alone cannot. For example, an accompanying image of a board game can help resolve the ambiguity of the word "monopoly," allowing the system to correctly identify it as a named entity. This approach targets the specific scope of social media posts where image and text are composed together, such as Snapchat captions or Twitter posts with image URLs.

### Mechanism: Modality Attention
A key component of the proposed method is the **Modality Attention** module. This module operates at each decoding step to select the most informative modality among available sources: word embeddings, character embeddings, or visual features.
*   **Noise Suppression:** For unknown or noisy tokens like "Marshmelloooo," the module attenuates word-level signals (which would be unreliable due to the "UNK" token) and amplifies character-level features. It leverages cues such as the capitalized first letter and lexical similarity to known entities ("Marshmello") to make a correct prediction.
*   **Contextual Relevance:** When an auxiliary image is available, the module determines whether to amplify visual context (e.g., for disambiguating polysemous entities) or attenuate it if the image is irrelevant (e.g., a selfie).
*   **Distinction from Standard Attention:** The paper explicitly notes that this modality attention is distinct from standard sequence-to-sequence attention, which typically attends to specific tokens within an input sequence. Instead, this module chooses *which modality* to prioritize. The source states that previous literature often combines word and character information via naive concatenation, which is vulnerable to noise, whereas this attention mechanism dynamically weights the inputs.

### Figure 1: Illustration of the Approach
**Figure 1** illustrates the multimodal NER framework with modality attention. It provides two concrete examples:
1.  **Polysemy Resolution:** It shows how visual contexts help recognize polysemous entity names, specifically contrasting "Monopoly" as a board game versus an economics term.
2.  **Noise Handling:** It demonstrates how modality attention suppresses word embeddings for an unknown token ("Marshmelloooo") and focuses on character-based context (capitalization, lexical similarity to "Marshmello") for correct prediction. This figure serves as the primary visual evidence for the mechanism's effectiveness in handling the two identified noise types.

### Contributions and Novelty Claims
The paper claims three main contributions:
1.  **LSTM-CNN Hybrid Multimodal NER Network:** A neural architecture that takes both image and text as input for named entity recognition.
2.  **First Visual Context Integration:** The authors state that, to the best of their knowledge, this is the first work to incorporate visual contexts for named entity recognition tasks.
3.  **Modality Attention Module:** The proposal of a general module that selects the most informative modality per decoding step.

*Note on Novelty:* The claim of being the "first" to incorporate visual contexts is a strong assertion. The source text does not provide a detailed comparison with specific prior works in this chunk to substantiate this claim, leaving the verification of this novelty dependent on the Related Work section (Section 2), which is not included in this scope.

### Remaining Dependencies
*   **SnapCaptions Dataset:** The source mentions "Snapchat captions" as an example of multimodal data but does not formally define the "SnapCaptions" dataset in this introduction chunk. Its specific characteristics, size, and construction remain an open dependency for this section.
*   **External Methodology Definitions:** The paper references standard NER architectures (LSTM, CharLSTM/CNN) and attention mechanisms. While their paper-local roles are described (e.g., as baselines or components to be improved), the full external definitions of these standard methods are assumed knowledge and are not detailed in this section.

**One-line summary:** The paper introduces a multimodal NER framework that uses visual context and a modality attention mechanism to resolve polysemy and handle noisy tokens in short social media text, claiming to be the first to integrate visual cues for this task.

_source: 2 Related Work_

### 2 Related Work

#### Neural NER Baselines and Limitations
The paper situates MNER within the landscape of recent neural Named Entity Recognition (NER) models, which have achieved state-of-the-art performance on standard tasks. Key prior works cited include Passos et al. (2014), Chiu and Nichols (2015), Huang et al. (2015), Lample et al. (2016), and Ma and Hovy (2016). These systems typically employ recurrent neural networks (RNNs) combined with Conditional Random Fields (CRF) for sequence labeling. They utilize feature extractors such as CNNs or LSTMs for word and character representations, often achieving high accuracy without relying on gazetteers. However, the source notes that most of these models aggregate textual context simply by concatenating word and character embeddings. This approach is identified as a limitation when dealing with noisy short text segments, such as tweets, where token substitution or missing embeddings are common. While some studies (Baldwin et al., 2015; Aguilar et al., 2017) address noisy text using external lexical information or preprocessing, the MNER model distinguishes itself by incorporating visual contexts and a specific modality attention module to handle missing tokens in the word embedding matrix more effectively.

**남은 의존성:** The specific architectural details of the Bi-LSTM-CRF baseline are referenced as standard practice but are not fully defined in this section; the reader must rely on external knowledge of Lafferty et al. (2001) and McCallum and Li (2003) for the complete methodology.

#### Attention Mechanisms in NLP
Attention modules are widely applied in deep learning tasks, including image captioning and machine translation (Xu et al., 2015; Chan et al., 2015; Sukhbaatar et al., 2015; Yao et al., 2015). In these contexts, attention typically allows a model to focus on a subset of a single input (e.g., a specific image region or token) during decoding. Rei et al. (2016) explored various attention mechanisms in NLP but did not incorporate visual components or investigate their impact on noisy social media data. Moon and Carbonell (2017) proposed using attention for subsets of discrete source samples in transfer learning. The paper argues that its proposed "modality attention" differs fundamentally from these approaches. Instead of attending to parts of a single modality, MNER attenuates or amplifies entire modality inputs (e.g., the whole visual stream vs. the whole textual stream). This mechanism maps heterogeneous modalities into a single joint embedding space, allowing the model to preserve semantic consistency even if some modalities are missing.

#### Multimodal Learning Paradigms
Multimodal learning aims to build joint models that extract contextual information from multiple views of parallel datasets. The paper identifies multimodal machine translation as the most relevant prior task (Elliott et al., 2015; Specia et al., 2016). In these systems, a sentence in a source language and a corresponding image are used to improve translation quality, often using standard sequence-to-sequence architectures where an image is fed into the decoder. Additionally, the paper cites Canonical Correlation Analysis (CCA) (Dhillon et al., 2011) as a method for learning feature correlations among multiple modalities. While these works establish the foundation for combining text and vision, the source implies that they do not specifically address the unique challenges of NER in noisy, short-form social media posts, which MNER targets.

**One-line summary:** This section positions MNER by highlighting that while neural NER and multimodal translation models exist, MNER uniquely uses modality attention to integrate visual and textual contexts for noisy short-text NER, distinguishing itself from standard self-attention and prior multimodal approaches.

_source: 3 Proposed Methods_

### 3.1 Feature Extraction Pipelines

The MNER model extracts three distinct types of features for each input token $t$: word embeddings, character embeddings, and visual features.

*   **Word Embeddings:** The model utilizes pre-trained GloVE vectors. These vectors are derived from unsupervised learning on large external corpora to capture distributional semantics.
    *   *남은 의존성:* The paper cites GloVE (Pennington et al., 2014) as the source for word embeddings but does not define the full external methodology of GloVE within this section.
*   **Character Embeddings:** A Bi-LSTM processes the character sequence of each token. The authors explicitly state that they chose Bi-LSTM over convolutional neural networks (CNNs), as used in prior work like Ma and Hovy (2016), because Bi-LSTM yielded empirically better results in their experiments.
*   **Visual Features:** Visual information is extracted using a modified Inception (GoogLeNet) model. This network consists of 22 layers and was trained on ImageNet to classify objects. The representation from the final hidden layer is used as the visual embedding.
    *   *남은 의존성:* The paper references Inception/GoogLeNet (Szegedy et al., 2014, 2015) and ImageNet (Russakovsky et al., 2015) but does not provide the full external definitions of these architectures or datasets.

Before being fed into the main NER LSTM, each feature vector ($\mathbf{x}_t^{(w)}, \mathbf{x}_t^{(c)}, \mathbf{x}_t^{(v)}$) passes through a transformation layer $\sigma$.

### 3.2 Bi-LSTM-CRF Backbone

The core architecture is a hybrid of a Bi-LSTM and a Conditional Random Field (CRF).

1.  **Input Aggregation:** At each decoding step, the model computes the weighted average of the three modalities, denoted as $\overline{\mathbf{x}_t}$. This aggregation is performed by the Modality Attention Module (defined in Section 3.3).
2.  **Bi-LSTM Processing:** The aggregated vector $\overline{\mathbf{x}_t}$ is input into the entity Bi-LSTM. The model produces forward ($\overrightarrow{\mathbf{h}_t}$) and backward ($\overleftarrow{\mathbf{h}_t}$) hidden states. These are concatenated to form the bi-directional representation $\overleftrightarrow{\mathbf{h}_t} = [\overrightarrow{\mathbf{h}_t}; \overleftarrow{\mathbf{h}_t}]$.
3.  **CRF Decoding:** The bi-directional representations are passed to a CRF layer. The CRF enforces structural dependencies between labels (e.g., BIO format constraints) by maximizing a log-likelihood objective. The potential function $\psi_t$ and parameter set $\mathbf{W}_{\text{CRF}}$ define the transition weights between label pairs.

### 3.3 Modality Attention Module

The Modality Attention Module is the key mechanism that combines the three modalities. It learns a unified representation space and produces a single vector based on the weighted importance of each modality.

**Motivation for Attention:**
The authors argue against naive concatenation of modalities (e.g., $\mathbf{h}_t = \text{LSTM}([\mathbf{x}_t^{(w)}; \mathbf{x}_t^{(c)}; \mathbf{x}_t^{(v)}])$) for two reasons:
1.  **OOV/Noise Handling:** In social media data, many tokens are unknown or missing. Naive concatenation forces the LSTM to process zero or random vectors for missing word embeddings, leading to inaccurate decoding.
2.  **Irrelevant Context:** Not all images contain relevant context for the text. Treating all modalities as equally informative in a simple concatenation yields suboptimal results.

The attention module allows the model to adaptively "turn on or off" modalities for each sample, effectively weighting the contribution of word, character, and visual features dynamically.

### 3.4 Architectural Overview (Figure 2)

**Figure 2** illustrates the main architecture of the MNER network. It shows the flow from raw inputs (word, character, image) through the feature extraction pipelines. The figure highlights that at each decoding step, the three modality representations are merged via the Modality Attention Module. The resulting vector is then processed by the Bi-LSTM/CRF backbone to produce the final entity label for each token. This visual confirms that the visual features are aligned with token-level text vectors at every step, rather than being used only as a global initial input.

**One-line summary:** The MNER model integrates GloVE word embeddings, Bi-LSTM character embeddings, and InceptionNet visual features using a dynamic Modality Attention Module, which feeds into a Bi-LSTM-CRF backbone to handle noisy social media text and irrelevant visual contexts.

_source: 4 Empirical Evaluation_

### 4.1 Dataset Construction and Statistics

The SnapCaptions dataset comprises 10,000 user-generated image-caption pairs collected from public Snapchat stories (e.g., "New York Story") between 2016 and 2017. Named entities within the captions were manually labeled by expert annotators into four categories: Person (PER), Location (LOC), Organization (ORG), and Miscellaneous (MISC). The dataset is partitioned into training (70%), validation (15%), and test (15%) sets. Captions average 30.7 characters (5.81 words) in length, with a vocabulary size of 15,733 tokens; of these, 6,612 are unknown to the Stanford GloVE embeddings. A distinguishing characteristic of this dataset is the prevalence of emerging entities, nicknames, and typos, which are common in social media but rare in standard NER benchmarks. The dataset does not include raw images; instead, it provides obfuscated visual descriptor features extracted from a pre-trained InceptionNet.

### 4.2 Task Definition and Baseline Models

The task is defined as labeling every token in a caption using the BIO (Beginning, Inside, Outside) scheme. The evaluation compares the proposed MNER model against several state-of-the-art text-only baselines to isolate the contributions of the visual modality and the modality attention mechanism. The baselines include:
*   **Bi-LSTM/CRF (W only):** Utilizes only word token embeddings (Stanford GloVE).
*   **Bi-LSTM/CRF + Bi-CharLSTM (C only):** Utilizes only character sequences, excluding word embeddings.
*   **Bi-LSTM/CRF + Bi-CharLSTM (W+C):** Combines word and character embeddings (Lample et al., 2016).
*   **Bi-LSTM/CRF + CharCNN (W+C):** Utilizes character embeddings derived from a CNN (Ma and Hovy, 2016).
*   **Bi-LSTM/CRF + CharCNN (W+C) + Multi-task:** Performs both entity type recognition and binary segmentation (Aguilar et al., 2017).

The proposed models introduce visual context and modality attention:
*   **Proposed (W+C) with Modality Attention:** Merges word and character embeddings using the attention module.
*   **Proposed (W+C+V):** Concatenates visual features from InceptionNet with word and character vectors.
*   **Proposed (W+C+V) with Modality Attention:** Uses the attention module to adaptively weight word, character, and visual embeddings before feeding them into the entity LSTM.

### 4.3 Experimental Setup and Hyperparameters

Model parameters were tuned using a search space for character/word embedding dimensions, LSTM hidden states, and output dimension $\bar{x}$, with values ranging from 25 to 300. The final configuration selected dimensions of 150 for embeddings and output, and 100 for LSTM hidden states. Optimization was performed using the Adagrad optimizer with a batch size of 10, a learning rate of 0.02, an epsilon of $10^{-8}$, and a decay rate of 0.0.

### 4.4 Performance Results and Artifact Analysis

**Table 1** reports the Precision, Recall, and F1 scores for both entity type recognition and entity segmentation tasks across different modality configurations. The results demonstrate that incorporating visual context (W+C+V) significantly improves performance over text-only models (W+C), confirming that visual features are complementary to textual information in NER. Furthermore, adding the modality attention module to the W+C+V configuration yields additional improvements in entity type recognition, indicating that the module effectively focuses on the most relevant modality for each sample. Notably, even the text-only model (W+C) equipped with modality attention outperforms the state-of-the-art baselines (Aguilar et al., 2017; Ma and Hovy, 2016; Lample et al., 2016), highlighting the effectiveness of the attention mechanism for textual data alone.

**Table 3** examines the impact of word embedding vocabulary size on NER performance (F1) for W+C models with and without modality attention. While the source text does not provide specific numerical values from Table 3, it establishes that vocabulary size is a critical hyperparameter affecting model performance, particularly given the high proportion of unknown tokens in the SnapCaptions dataset.

### 4.5 Error Analysis and Qualitative Insights

**Table 2** provides a qualitative error analysis illustrating when visual contexts aid or hinder NER predictions. The table compares ground-truth labels with predictions from the W+C+V and W+C models, using InceptionNet visual tags for interpretability.
*   **Polysemy Resolution:** In the caption "The curry's," the token 'curry' is polysemous (referring to either food or Stephen Curry). Textual context alone is insufficient for disambiguation. However, visual tags such as 'parade' and 'urban area' align with the distributional semantics of NBA-related snaps, allowing the W+C+V model to correctly identify 'curry' as a named entity.
*   **Disambiguation of Common Nouns:** In "Grandma w dat lit Apple Crisp," the text-only model incorrectly predicts 'Apple' as an organization (Apple Inc.). Visual contexts describing food objects help the W+C+V model correctly classify 'Apple' as a non-named entity (fruit).
*   **Trending Entities:** Visual contexts describing concert scenes facilitate the recognition of trending musicians (e.g., 'CID', 'Marshmello') even when surrounding textual context is sparse.
*   **Failure Cases:** Visual contexts can degrade performance when visual tags are unrelated to the token or its textual context, leading to incorrect predictions.

### 4.6 Visualization of Modality Attention

**Figure 3** visualizes the modality attention mechanism at each decoding step. Darker colors indicate amplified modalities, while lighter colors indicate attenuated ones. For the W+C+V model, the figure shows that the attention module successfully attenuates irrelevant signals (e.g., generic selfie features) and amplifies relevant modality-based contexts for specific tokens. This visualization supports the claim that the model adaptively weights modalities to maximize information gain. The figure also includes unsuccessful cases, demonstrating that while the mechanism is generally effective, it is not infallible.

**Remaining Dependency:** The full external definition of the InceptionNet architecture and the specific methodology for extracting obfuscated visual descriptors are not detailed in this section; only their role as feature providers is described.

**One-line summary:** The SnapCaptions dataset and MNER model demonstrate that visual context and modality attention significantly improve NER performance on social media captions, particularly for resolving polysemy and recognizing emerging entities, as evidenced by F1 scores in Table 1 and qualitative examples in Table 2 and Figure 3.

_source: 5 Conclusions_

### Task Definition and Core Contribution
The authors conclude by reiterating the paper’s primary contribution: the proposal of a new multimodal Named Entity Recognition (MNER) task specifically designed for short social media posts. This task integrates both image and text modalities. The paper claims to demonstrate, for the first time, an effective MNER system that combines visual and textual information. The central argument is that this multimodal approach outperforms traditional text-based NER baselines, establishing the utility of visual context in entity recognition for social media content.

### Mechanism: Modality Attention Module
A key technical contribution highlighted in the conclusion is the "modality attention module." This is described as a new neural mechanism designed to learn the optimal integration of different modes of correlated information. The mechanism operates by learning to attenuate irrelevant or uninformative modal information while simultaneously amplifying the primary modality. The goal of this process is to extract better overall representations for the NER task. This module is presented as the core driver behind the system's ability to effectively fuse visual and textual data.

### Performance and Generalizability
The authors state that the modality attention-based model outperforms other state-of-the-art baselines. Specifically, they note that even when text was the only modality available, the model achieved superior performance by better combining word and character-level information. This suggests that the architectural improvements benefit the system even in unimodal scenarios. Furthermore, the authors argue that the work has broad applicability. They claim the system can be applied to a wide variety of social media posts or other articles across multiple platforms, particularly those that frequently include both text and accompanying images.

### Scope Limitations and Future Work
The provided source statements for this section focus exclusively on summarizing the proposed task, the mechanism, and the performance results. The text does not explicitly list specific limitations acknowledged by the authors, nor does it detail specific future research directions beyond the general statement of applicability to other platforms. There is no mention of specific constraints regarding data size, computational cost, or specific failure cases in this chunk.

### Dataset Availability and Reproducibility
The source statements do not contain any explicit information regarding the release of the dataset. There is no mention of whether the SnapCaptions dataset (or any other dataset used) is publicly available, nor are there details about the format of the release (e.g., raw images vs. extracted features). Consequently, the question of whether raw images are available for reproducibility remains unanswered in this specific text segment. The conclusion focuses on the model's utility rather than the logistical aspects of data sharing.

**One-line summary:** The authors conclude that their proposed MNER task and modality attention module effectively integrate visual and textual data to outperform text-only baselines, though this section does not specify dataset availability or detailed future work.

## 핵심 개념 상세

### MNER is a new task for recognizing named entities in short text with accompanying images from noisy user-generated data.
- **무엇인가:** Named entities annotated in the SnapCaptions dataset include many of new and emerging entities, and they are found in various surface forms (various nicknames, typos, etc.) To the best of our knowledge, SnapCaptions is the only dataset that contains natural image-caption pairs with expert-annotated named entities.
- **논문에서의 역할:** A new dataset called SnapCaptions was created, consisting of Snapchat image-caption pairs with fully annotated named entities.
- **정의/설명 근거:**
  - Named entities annotated in the SnapCaptions dataset include many of new and emerging entities, and they are found in various surface forms (various nicknames, typos, etc.) To the best of our knowledge, SnapCaptions is the only dataset that contains natural im
- **관련 그림/수식:**
  - Figure 1: Figure 1: Multimodal NER + modality attention . (a) Visual contexts help recognizing polysemous entity names (‘Monopoly’ as in a board game versus an economics term). (b) Modality attention successfully suppresses word embeddings of a unknown token (‘Marshmelloooo’ with erroneously trailing ‘o’s), and focuses on chara…
  - Figure 2: Figure 2: The main architecture for our multimodal NER (MNER) network with modality attention. At each decoding step, word embeddings, character embeddings, and visual features are merged with modality attention. Bi-LSTM/CRF takes as input each token and produces an entity label.
  - Table 1: Table 1: NER performance on the SnapCaptions dataset with varying modalities (W: word, C: char, V: visual). We report precision, recall, and F1 score for both entity types recognition (PER, LOC, ORG, MISC) and entity segmentation (untyped recognition - named entity or not) tasks.
- **추적 ID:** source: `s0001_01`, `s0001_02`, `s0002_03`, `s0003_05`, `s0006_01`, `s0001_03`, `s0006_04`, `s0052_01`; artifact: `fig0001`, `fig0002`, `tbl0001`, `tbl0002`

### The paper does not explicitly define a restricted boundary of entity types in this chunk; it frames MNER as recognizing named entities from short, noisy social media text using mu…
- **무엇인가:** The paper does not explicitly define a restricted boundary of entity types in this chunk; it frames MNER as recognizing named entities from short, noisy social media text using multimodal context.
- **논문에서의 역할:** MNER is a new task for recognizing named entities in short text with accompanying images from noisy user-generated data.
- **관련 그림/수식:**
  - Figure 1: Figure 1: Multimodal NER + modality attention . (a) Visual contexts help recognizing polysemous entity names (‘Monopoly’ as in a board game versus an economics term). (b) Modality attention successfully suppresses word embeddings of a unknown token (‘Marshmelloooo’ with erroneously trailing ‘o’s), and focuses on chara…
  - Figure 2: Figure 2: The main architecture for our multimodal NER (MNER) network with modality attention. At each decoding step, word embeddings, character embeddings, and visual features are merged with modality attention. Bi-LSTM/CRF takes as input each token and produces an entity label.
  - Table 1: Table 1: NER performance on the SnapCaptions dataset with varying modalities (W: word, C: char, V: visual). We report precision, recall, and F1 score for both entity types recognition (PER, LOC, ORG, MISC) and entity segmentation (untyped recognition - named entity or not) tasks.
- **추적 ID:** source: `s0002_03`, `s0003_05`, `s0006_01`, `s0001_01`, `s0001_02`, `s0003_06`, `s0003_07`, `s0006_02`; artifact: `fig0001`, `fig0002`, `tbl0001`, `tbl0002`

### Prior neural NER models typically use RNNs with CRFs and aggregate context via concatenation of word and character embeddings.
- **무엇인가:** Visual features are extracted per image and fed at every decoding step. A modality attention module computes a weighted average of word, character, and visual embeddings to create a unified context vector for the Bi-LSTM.
- **논문에서의 역할:** Standard NER models struggle with social media text may be due to extreme brevity, polysemy, and noisy/unknown tokens.
- **어떻게 동작하는가:**
  - A modality attention module selects the most informative modality (word, character, or visual) per decoding step to suppress noise and resolve ambiguity.
  - Visual features are extracted per image and fed at every decoding step. A modality attention module computes a weighted average of word, character, and visual embeddings to create a unified context vector for the Bi-LSTM.
  - Modality attention adaptively weights word, character, and visual embeddings to produce a unified context vector, avoiding naive concatenation issues.
  - Note that most of these work aggregate textual contexts via concatenation of word embeddings and character embeddings.
- **구현/메커니즘 근거:**
  - Note that most of these work aggregate textual contexts via concatenation of word embeddings and character embeddings.
  - Note that most of the previous literature in NER or other NLP tasks combine word and character-level information with naive concatenation, which is vulnerable to noisy social media posts.
- **관련 그림/수식:**
  - Figure 1: Figure 1: Multimodal NER + modality attention . (a) Visual contexts help recognizing polysemous entity names (‘Monopoly’ as in a board game versus an economics term). (b) Modality attention successfully suppresses word embeddings of a unknown token (‘Marshmelloooo’ with erroneously trailing ‘o’s), and focuses on chara…
  - Figure 2: Figure 2: The main architecture for our multimodal NER (MNER) network with modality attention. At each decoding step, word embeddings, character embeddings, and visual features are merged with modality attention. Bi-LSTM/CRF takes as input each token and produces an entity label.
  - Figure 3: Figure 3: Visualization of modality attention (a) successful cases and (b) unsuccessful ones from SnapCaptions test data. For each decoding step of a token (column), the modality attention module amplifies the most relevant modality (darker) while attenuating irrelevant modalities (lighter). The model makes final pred…
- **추적 ID:** source: `s0007_05`, `s0007_07`, `s0013_04`, `s0019_04`, `s0022_01`, `s0029_01`, `s0030_01`, `s0003_05`; artifact: `fig0001`, `fig0002`, `fig0003`, `tbl0003`

### MNER model integrates word, character, and visual embeddings via a modality attention module to handle multimodal NER.
- **무엇인가:** Visual features are extracted per image and fed at every decoding step. A modality attention module computes a weighted average of word, character, and visual embeddings to create a unified context vector for the Bi-LSTM.
- **논문에서의 역할:** The authors propose a model using a deep image network and a generic modality-attention module to augment textual NER.
- **어떻게 동작하는가:**
  - A modality attention module selects the most informative modality (word, character, or visual) per decoding step to suppress noise and resolve ambiguity.
  - Modality attention attenuates/amplifies entire modality inputs and maps heterogeneous modalities to a joint embedding space, unlike standard attention which attends to subsets within a single input.
  - Visual features are extracted per image and fed at every decoding step. A modality attention module computes a weighted average of word, character, and visual embeddings to create a unified context vector for the Bi-LSTM.
  - The modality attention module learns optimal integration of correlated modalities by attenuating irrelevant information.
- **관련 그림/수식:**
  - Figure 1: Figure 1: Multimodal NER + modality attention . (a) Visual contexts help recognizing polysemous entity names (‘Monopoly’ as in a board game versus an economics term). (b) Modality attention successfully suppresses word embeddings of a unknown token (‘Marshmelloooo’ with erroneously trailing ‘o’s), and focuses on chara…
  - Figure 2: Figure 2: The main architecture for our multimodal NER (MNER) network with modality attention. At each decoding step, word embeddings, character embeddings, and visual features are merged with modality attention. Bi-LSTM/CRF takes as input each token and produces an entity label.
  - Figure 3: Figure 3: Visualization of modality attention (a) successful cases and (b) unsuccessful ones from SnapCaptions test data. For each decoding step of a token (column), the modality attention module amplifies the most relevant modality (darker) while attenuating irrelevant modalities (lighter). The model makes final pred…
- **추적 ID:** source: `s0013_01`, `s0013_03`, `s0013_04`, `s0019_04`, `s0022_01`, `s0029_01`, `s0030_01`, `s0001_04`; artifact: `fig0001`, `fig0002`, `fig0003`, `tbl0003`
