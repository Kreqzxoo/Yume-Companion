# Third-party components of the Yume LLM Server

The Yume LLM Server itself is proprietary (see [LICENSE](LICENSE)). It does not ship the components below;
it downloads them when you use the matching function, and they stay under their own licenses.

| Component | License | How it is used |
| --- | --- | --- |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) (`llama-server`) | MIT | downloaded from GitHub on first start, runs as a separate process |
| [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) | MIT | downloaded from GitHub for image generation, runs as a separate process |
| Language, vision and image models (Qwen, Gemma, Llama, Stable Diffusion, ...) | each model's own license (e.g. Apache-2.0, Gemma Terms of Use, Llama Community License, CreativeML Open RAIL) | downloaded from Hugging Face on your request; you are responsible for complying with them |
| Microsoft .NET Framework / Windows components | Microsoft license terms | part of Windows, used to run the program |
| Inno Setup | Inno Setup License | used to build the installer; not part of the installed program |
