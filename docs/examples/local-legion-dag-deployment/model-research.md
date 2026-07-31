# DeepSeek V4 Release Notes

This summary records the primary-source facts relevant to the local model
selection. It intentionally omits unsourced benchmark and pricing claims.

## Sources

- [DeepSeek V4 Preview release announcement](https://api-docs.deepseek.com/news/news260424)
- [DeepSeek API changelog](https://api-docs.deepseek.com/updates)
- [Official DeepSeek V4 Flash model card](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash)
- [Official DeepSeek V4 Pro model card](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro)

## Release facts

DeepSeek announced the V4 Preview family on 2026-04-24. Both
`deepseek-v4-pro` and `deepseek-v4-flash` were available through the DeepSeek
API that day, and both official model repositories were published under the
DeepSeek organization on Hugging Face.

| | V4 Flash | V4 Pro |
|---|---|---|
| Total parameters | 284B | 1.6T |
| Activated parameters | 13B | 49B |
| Context length | 1M | 1M |
| Official positioning | Faster, economical option; close to Pro on simple agent tasks | Stronger model for agentic coding, knowledge, and reasoning |
| API model ID | `deepseek-v4-flash` | `deepseek-v4-pro` |

There was no primary-source support for a separate
`DeepSeek-V4-Flash-0731` release, a 2026-07-31 public-beta launch, or the claim
that Flash beat Pro on nine agent benchmarks. Those claims have been removed.

## Relevance to this case study

The local deployment used Flash for higher-volume roles and Pro for selected
fallbacks. That is a cost and routing choice made by the operator, not an
official DeepSeek recommendation or a project-wide Legion default.
