# Feature Specification: AWS Bedrock Provider Support

**Feature Branch**: `105-aws-bedrock`
**Created**: 2025-12-18
**Status**: Draft
**Input**: Product Roadmap Phase 7

## User Scenarios & Testing

### User Story 1 - Bedrock Embedding Models (Priority: P1)

A user on AWS wants to use Bedrock embedding models (Titan, Cohere) instead of OpenAI for cost or compliance reasons.

**Why this priority**: Core Bedrock integration. Enables AWS-native deployments.

**Independent Test**: Configure Bedrock Titan embeddings, index documents, verify embeddings generated via Bedrock.

**Acceptance Scenarios**:

1. **Given** config with `embedding.provider: bedrock`, **When** I index documents, **Then** Titan Embed is used
2. **Given** Bedrock configured, **When** I specify model `amazon.titan-embed-text-v2`, **Then** that model is used
3. **Given** Bedrock configured, **When** I specify model `cohere.embed-english-v3`, **Then** Cohere via Bedrock is used
4. **Given** Bedrock embeddings, **When** I query, **Then** same embedding model is used for query encoding

---

### User Story 2 - Bedrock LLM for Summarization (Priority: P1)

A user wants to use Bedrock-hosted LLMs (Claude, Titan Text, Llama) for summarization.

**Why this priority**: Completes Bedrock integration. Users may prefer Claude via Bedrock for enterprise billing.

**Independent Test**: Configure Bedrock Claude for summarization, index documents, verify summaries generated.

**Acceptance Scenarios**:

1. **Given** config with `summarization.provider: bedrock`, **When** indexing, **Then** Bedrock LLM generates summaries
2. **Given** Bedrock configured with Claude, **When** I index code, **Then** Claude via Bedrock summarizes
3. **Given** Bedrock configured with Titan Text, **When** I index documents, **Then** Titan generates summaries
4. **Given** Bedrock configured with Llama, **When** I index, **Then** Meta Llama via Bedrock generates summaries

---

### User Story 3 - AWS IAM Authentication (Priority: P1)

Users authenticate to Bedrock using AWS IAM credentials (default credentials chain, profiles, or explicit keys).

**Why this priority**: Standard AWS authentication pattern. Required for enterprise deployments.

**Independent Test**: Configure with IAM profile, verify Bedrock calls succeed.

**Acceptance Scenarios**:

1. **Given** AWS default credentials configured, **When** server starts with Bedrock, **Then** authentication succeeds
2. **Given** AWS profile specified in config, **When** server starts, **Then** that profile is used
3. **Given** explicit access key and secret, **When** configured via env vars, **Then** authentication succeeds
4. **Given** IAM role (EC2/ECS), **When** server runs on AWS, **Then** instance credentials are used

---

### User Story 4 - Region Configuration (Priority: P2)

Users can specify the AWS region for Bedrock API calls.

**Why this priority**: Bedrock availability varies by region. Users need control over data residency.

**Independent Test**: Configure different regions, verify API calls go to specified region.

**Acceptance Scenarios**:

1. **Given** config with `params.region: us-east-1`, **When** server starts, **Then** Bedrock calls go to us-east-1
2. **Given** config with `params.region: eu-west-1`, **When** server starts, **Then** Bedrock calls go to eu-west-1
3. **Given** no region specified, **When** server starts, **Then** AWS default region is used
4. **Given** region without Bedrock, **When** server starts, **Then** clear error about region availability

---

### User Story 5 - Cross-Region Inference (Priority: P3)

Users can enable cross-region inference for higher availability and capacity.

**Why this priority**: Advanced Bedrock feature for production workloads. Lower priority than basic integration.

**Independent Test**: Enable cross-region inference, verify requests routed appropriately.

**Acceptance Scenarios**:

1. **Given** cross-region enabled, **When** primary region busy, **Then** requests routed to alternative
2. **Given** cross-region disabled, **When** primary region busy, **Then** requests queue or fail
3. **Given** cross-region enabled, **When** I query, **Then** response includes routing information

---

### Edge Cases

- What happens when Bedrock model not enabled in account? (Clear error with activation instructions)
- How does system handle Bedrock throttling? (Exponential backoff, respect rate limits)
- What happens when AWS credentials expire? (Refresh automatically, fail gracefully if unable)
- How does system handle Bedrock model deprecation? (Warn on startup, suggest migration)
- What happens when Bedrock returns error? (Log error, retry if transient, fail if persistent)

## Requirements

### Functional Requirements

- **FR-001**: System MUST support AWS Bedrock as embedding provider
- **FR-002**: System MUST support Titan Embed Text v1/v2 models
- **FR-003**: System MUST support Cohere Embed models via Bedrock
- **FR-004**: System MUST support AWS Bedrock as summarization provider
- **FR-005**: System MUST support Claude, Titan Text, Llama, Mistral, Cohere via Bedrock
- **FR-006**: System MUST support AWS default credentials chain
- **FR-007**: System MUST support AWS profile-based authentication
- **FR-008**: System MUST support explicit access key/secret via environment variables
- **FR-009**: System MUST support region configuration
- **FR-010**: System MUST handle Bedrock throttling with exponential backoff

### Supported Models

**Embeddings:**
| Model ID | Dimensions | Notes |
|----------|------------|-------|
| amazon.titan-embed-text-v1 | 1536 | Standard Titan embeddings |
| amazon.titan-embed-text-v2 | 1024/256 | Configurable dimensions |
| cohere.embed-english-v3 | 1024 | English optimized |
| cohere.embed-multilingual-v3 | 1024 | Multilingual support |

**Summarization/LLM:**
| Model ID | Provider | Notes |
|----------|----------|-------|
| anthropic.claude-3-haiku | Anthropic | Fast, cost-effective |
| anthropic.claude-3-sonnet | Anthropic | Balanced |
| anthropic.claude-3-opus | Anthropic | Most capable |
| amazon.titan-text-express | Amazon | Fast inference |
| amazon.titan-text-premier | Amazon | Higher quality |
| meta.llama3-8b-instruct | Meta | Open source |
| meta.llama3-70b-instruct | Meta | Larger capacity |
| mistral.mistral-large | Mistral | Multilingual |

### Configuration Example

```yaml
embedding:
  provider: bedrock
  model: amazon.titan-embed-text-v2
  params:
    region: us-east-1
    profile: default  # Optional AWS profile

summarization:
  provider: bedrock
  model: anthropic.claude-3-haiku-20240307-v1:0
  params:
    region: us-east-1
```

### Key Entities

- **BedrockEmbedding**: LlamaIndex Bedrock embedding integration
- **BedrockLLM**: LlamaIndex Bedrock LLM integration
- **AWSCredentialsProvider**: Handles credential chain resolution
- **BedrockConfig**: Region, profile, and model configuration

## Success Criteria

### Measurable Outcomes

- **SC-001**: Bedrock embeddings work with all supported Titan and Cohere models
- **SC-002**: Bedrock LLM summarization works with Claude, Titan, Llama, Mistral
- **SC-003**: AWS IAM authentication works with all credential methods
- **SC-004**: Bedrock throttling is handled gracefully without data loss
- **SC-005**: All Phase 1-6 functionality remains working with Bedrock providers
- **SC-006**: Documentation includes Bedrock setup and IAM policy requirements
