# Logbook: RFD 0016 model-repo build-out

Source: [RFD 0016's inventory table](https://github.com/weftspun/request-for-discussion/blob/main/0016-deep-learning-model-inventory/DETAILS.md)
(15 models). Per the user's explicit override, one standalone repo per model — not RFD 0036's
"one repo, many folders" convention.

## Scope decided

- **15 catalog entries total.**
- **1 already satisfied elsewhere**: `misamaru_seethrough` — covered by the existing
  `interactor-seethrough-ggml` / `interactor-seethrough-torch` repos from earlier in this work.
- **4 abandoned**, no repo created, per each RFD's own `State: abandoned` field
  (RFD 0064's pivot away from scene/world reconstruction toward character concepts):
  `worldmirror2_reconstruct`, `triposplat_image_to_splat`, `weftspun_image_to_world`,
  `lingbot_map_environment_scan`.
- **10 repos built** — the rest of this log.

## The 10 repos, in priority order

Priority = how ready each is to actually run for real, not the order built in. Ranked by: does it
unblock other repos, is the license clean and confirmed, and is the upstream API already verified
(vs. still an honest `NotImplementedError`).

| # | Repo | RFD | License | Why this rank |
|---|---|---|---|---|
| 1 | [interactor-trellis2-image-to-textured-mesh](https://github.com/weftspun/interactor-trellis2-image-to-textured-mesh) | 0038 | MIT | Dependency root — 3 other repos build `FROM weftspun/trellis2-base` or share its weights. Blocks the most work if left undone. Real upstream API verified against `microsoft/TRELLIS.2`'s own README, `_run_upstream()` implemented for real (not a stub). |
| 2 | [interactor-pixal3d-image-to-textured-mesh](https://github.com/weftspun/interactor-pixal3d-image-to-textured-mesh) | 0040 | MIT | Ported **verbatim** from RFD 0040, which was already the fully-worked complete example for RFD 0036. Ship-ready once built and smoke-tested — no `NotImplementedError` anywhere. |
| 3 | [interactor-qwen-image-edit](https://github.com/weftspun/interactor-qwen-image-edit) | 0043 | Apache-2.0, independently checked | Clean license, standalone (no dependency), high catalog value (2D image edit, distinct capability from every mesh model). Only gap: the diffusers `QwenImageEditPipeline` call against the Q4_K_M GGUF isn't verified yet. |
| 4 | [interactor-skintokens-auto-rig](https://github.com/weftspun/interactor-skintokens-auto-rig) | 0046 | MIT, confirmed against the real `LICENSE` file (RFD 0046 had it "review pending" — it isn't ambiguous) | Clean license, standalone, small model (1.0 GB bf16). Unblocks any downstream rigging pipeline. |
| 5 | [interactor-trellis2-image-mesh-painting](https://github.com/weftspun/interactor-trellis2-image-mesh-painting) | 0039 | MIT | Depends on #1. Real upstream API verified against `TRELLIS.2/app_texturing.py`. Known gap: the `xatlas` UV pre-check RFD 0039 calls for isn't implemented. |
| 6 | [interactor-voxhammer-text-mesh-editing](https://github.com/weftspun/interactor-voxhammer-text-mesh-editing) | 0047 | MIT, independently checked | Depends on #1. Composite (RFD 0037 taskweft HTN domain), `domain.ex`/`problem.ex`/`plan.ex` ported verbatim, dispatch order proven in stub mode. Gap: VoxHammer's real inversion/edit/splice/decode calls not yet wired. |
| 7 | [interactor-voxhammer-image-mesh-editing](https://github.com/weftspun/interactor-voxhammer-image-mesh-editing) | 0048 | MIT, independently checked | Depends on #1 and shares #6's `domain.ex` (RFD 0048 has no domain of its own — only `problem.ex`/`plan.ex` differ, `mode.conditioning: "image"` in place of `"text"`). Same gap as #6. |
| 8 | [interactor-kimodo-text-to-motion](https://github.com/weftspun/interactor-kimodo-text-to-motion) | 0045 | Code Apache-2.0; weights per-checkpoint — resolved to **Kimodo-SOMA** specifically (NVIDIA Open Model License, commercial-friendly). RFD 0045 hadn't recorded a weight license at all; do not swap to the Kimodo-SMPLX checkpoint without re-checking RFD 0028 — that variant is the more restrictive NVIDIA R&D Model License. | Small model, license now resolved to a shippable variant. Gaps: the sampler call, RFD 0007's validation gate, and the retarget path are all unwired. Retarget path corrected mid-build per user input to go SOMA → ANNY → Godot Humanoid → VRM via [meshula/LabRCSF](https://github.com/meshula/LabRCSF)'s `joints.csv` canonical-joint pivot table, not a direct name guess. |
| 9 | [interactor-krea2-turbo-text-to-image](https://github.com/weftspun/interactor-krea2-turbo-text-to-image) | 0042 | **Krea 2 Community License** — revenue-gated: free commercial use only under $1M company-wide annual revenue and <50 seats; larger orgs need a separate enterprise license. Not Apache/MIT. Flagged for RFD 0028's owner: this clears the bar for a small deployer, not for every possible customer. | Largest model in the catalog (33.8 GB bf16 → 9.30 GB Q4_K_M), most build complexity (4-part staged load), and the only license here that's conditionally gated rather than clean or resolved. Also: the exact HF repo id/filenames for the Q4_K_M GGUF set are an unconfirmed guess. |
| 10 | [interactor-p3sam-mesh-segmentation](https://github.com/weftspun/interactor-p3sam-mesh-segmentation) | 0041 | **Tencent Community License Agreement** (territory-restricted — excludes EU/UK/South Korea), not MIT as RFD 0041 states. Verified by reading the real `LICENSE` file at `Tencent-Hunyuan/Hunyuan3D-Part` directly; confirmed no separately-MIT standalone P3-SAM repo exists. | Lowest priority: the license is a real, unresolved gate (territory exclusions are a hard block for some customers, not a formality), and `_run_upstream()` isn't yet verified against P3-SAM's real `model.py`. Needs RFD 0041's owner to correct the license field before this can ship. |

## License corrections made to the org's own record

Two RFDs stated a license that didn't match the real upstream when checked directly:

- **RFD 0041** says P3-SAM is MIT. Real upstream (`Tencent-Hunyuan/Hunyuan3D-Part`) is under
  Tencent's own Community License Agreement, territory-restricted. Not propagated — the new
  repo's README marks it "review pending" and documents the discrepancy.
- **RFD 0046** marks SkinTokens' license "review pending". Real upstream
  (`VAST-AI-Research/SkinTokens`) has a plain MIT `LICENSE` file — not ambiguous. Resolved to
  MIT in the new repo, documented for RFD 0046's owner to close out.

One RFD (0045, Kimodo) simply didn't record a weight license at all — resolved by reading
`nv-tlabs/kimodo`'s own README: code is Apache-2.0, but checkpoints are licensed **per variant**
(Kimodo-SOMA/-G1: NVIDIA Open Model License; Kimodo-SMPLX: NVIDIA R&D Model License, more
restrictive). The new repo pins to Kimodo-SOMA specifically and documents why.

## Known gaps left honest, not papered over

Every repo above the pixal3d line (which is verbatim-complete) has at least one
`NotImplementedError` in `server.py` for a step whose real upstream call wasn't verified in this
pass — each one names exactly what needs confirming and against which upstream repo. None of these
were guessed and left silent; `STUB` mode proves the request/response shape and (for the two
composite VoxHammer repos) the dispatch order, without needing the real model.

## Not done this pass (carried forward from earlier in the session, unrelated to RFD 0016)

- Retrofitting nlohmann/json + OpenSSL base64, and swapping libcurl for h2o as the HTTP client,
  across `transport-runpod` / `interactor-qwen35-defiant` / `interactor-gemma4-composer` /
  `runpod-chat-tui`. Started, not finished.
