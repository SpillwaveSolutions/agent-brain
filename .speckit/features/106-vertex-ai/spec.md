# Feature Specification: Google Vertex AI Provider Support

**Feature Branch**: `106-vertex-ai`
**Created**: 2025-12-18
**Status**: Draft
**Input**: Product Roadmap Phase 8

## User Scenarios & Testing

### User Story 1 - Vertex AI Embedding Models (Priority: P1)

A user on Google Cloud wants to use Vertex AI embedding models for their doc-serve deployment.

**Why this priority**: Core Vertex integration. Enables GCP-native deployments.

**Independent Test**: Configure Vertex embeddings, index documents, verify embeddings generated via Vertex.

**Acceptance Scenarios**:

1. **Given** config with `embedding.provider: vertex`, **When** I index documents, **Then** Vertex embeddings are used
2. **Given** Vertex configured with `textembedding-gecko@003`, **When** I index, **Then** that model generates embeddings
3. **Given** Vertex configured with multimodal model, **When** I index images, **Then** multimodal embeddings are generated
4. **Given** Vertex embeddings, **When** I query, **Then** same embedding model encodes the query

---

### User Story 2 - Vertex AI LLM for Summarization (Priority: P1)

A user wants to use Vertex AI Gemini models for summarization.

**Why this priority**: Completes Vertex integration. Gemini offers strong summarization capabilities.

**Independent Test**: Configure Vertex Gemini for summarization, index documents, verify summaries generated.

**Acceptance Scenarios**:

1. **Given** config with `summarization.provider: vertex`, **When** indexing, **Then** Gemini generates summaries
2. **Given** Vertex configured with Gemini 1.5 Flash, **When** I index code, **Then** fast summaries are generated
3. **Given** Vertex configured with Gemini 1.5 Pro, **When** I index complex docs, **Then** higher quality summaries
4. **Given** Vertex configured, **When** I index large documents, **Then** Gemini's 1M context handles them

---

### User Story 3 - GCP Service Account Authentication (Priority: P1)

Users authenticate to Vertex AI using GCP service accounts or Application Default Credentials.

**Why this priority**: Standard GCP authentication pattern. Required for enterprise deployments.

**Independent Test**: Configure with service account JSON, verify Vertex calls succeed.

**Acceptance Scenarios**:

1. **Given** GOOGLE_APPLICATION_CREDENTIALS set, **When** server starts with Vertex, **Then** ADC authentication succeeds
2. **Given** service account JSON path in config, **When** server starts, **Then** that account is used
3. **Given** workload identity (GKE), **When** server runs on GKE, **Then** workload identity credentials are used
4. **Given** compute engine default account, **When** server runs on GCE, **Then** metadata server credentials used

---

### User Story 4 - Project and Location Configuration (Priority: P2)

Users can specify the GCP project and location for Vertex AI API calls.

**Why this priority**: Required for correct billing and data residency. GCP projects are mandatory.

**Independent Test**: Configure different projects/locations, verify API calls go to correct project.

**Acceptance Scenarios**:

1. **Given** config with `params.project: my-project`, **When** server starts, **Then** Vertex calls use that project
2. **Given** config with `params.location: us-central1`, **When** server starts, **Then** Vertex calls go to that region
3. **Given** no project specified, **When** server starts, **Then** clear error about required project
4. **Given** project without Vertex API enabled, **When** server starts, **Then** error with API activation link

---

### User Story 5 - Multimodal Embedding Support (Priority: P3)

Users can generate embeddings for images and other multimodal content via Vertex.

**Why this priority**: Advanced capability leveraging Gemini's multimodal strengths. Lower priority than text.

**Independent Test**: Index documents with images, verify multimodal embeddings generated.

**Acceptance Scenarios**:

1. **Given** multimodal embedding model configured, **When** I index markdown with images, **Then** images get embeddings
2. **Given** multimodal embeddings, **When** I query with text, **Then** relevant images are returned
3. **Given** mixed content, **When** I index, **Then** both text and image embeddings are stored
4. **Given** text-only model configured, **When** I index images, **Then** images are skipped with warning

---

### Edge Cases

- What happens when Vertex API not enabled in project? (Clear error with API activation link)
- How does system handle Vertex quotas? (Respect rate limits, queue with backoff)
- What happens when service account lacks permissions? (Clear error about required IAM roles)
- How does system handle Vertex model updates? (Log model version, warn on deprecation)
- What happens when location doesn't support model? (Clear error listing available locations)

## Requirements

### Functional Requirements

- **FR-001**: System MUST support Google Vertex AI as embedding provider
- **FR-002**: System MUST support textembedding-gecko models
- **FR-003**: System MUST support multimodalembedding models (optional)
- **FR-004**: System MUST support Google Vertex AI as summarization provider
- **FR-005**: System MUST support Gemini 1.5 Flash and Pro models
- **FR-006**: System MUST support Application Default Credentials (ADC)
- **FR-007**: System MUST support explicit service account JSON configuration
- **FR-008**: System MUST require project and location configuration
- **FR-009**: System MUST handle Vertex quotas with appropriate backoff
- **FR-010**: System MUST log model version information for debugging

### Supported Models

**Embeddings:**
| Model ID | Dimensions | Notes |
|----------|------------|-------|
| textembedding-gecko@003 | 768 | Latest text embedding |
| textembedding-gecko@002 | 768 | Stable text embedding |
| textembedding-gecko-multilingual@001 | 768 | Multilingual support |
| multimodalembedding@001 | 1408 | Text + image embeddings |

**Summarization/LLM:**
| Model ID | Context | Notes |
|----------|---------|-------|
| gemini-1.5-flash | 1M tokens | Fast, cost-effective |
| gemini-1.5-pro | 2M tokens | Highest capability |
| gemini-1.0-pro | 32K tokens | Stable, lower cost |

### Configuration Example

```yaml
embedding:
  provider: vertex
  model: textembedding-gecko@003
  params:
    project: my-gcp-project
    location: us-central1

summarization:
  provider: vertex
  model: gemini-1.5-flash
  params:
    project: my-gcp-project
    location: us-central1
```

### Key Entities

- **VertexAIEmbedding**: LlamaIndex Vertex embedding integration
- **VertexAI**: LlamaIndex Vertex LLM integration
- **GCPCredentialsProvider**: Handles ADC and service account resolution
- **VertexConfig**: Project, location, and model configuration

## Success Criteria

### Measurable Outcomes

- **SC-001**: Vertex embeddings work with all supported gecko models
- **SC-002**: Vertex LLM summarization works with Gemini Flash and Pro
- **SC-003**: GCP authentication works with ADC, service accounts, and workload identity
- **SC-004**: Vertex quotas are handled gracefully without data loss
- **SC-005**: All Phase 1-6 functionality remains working with Vertex providers
- **SC-006**: Documentation includes Vertex setup and IAM requirements
- **SC-007**: Multimodal embeddings work for documents with images (optional feature)
