# ---------------------------------------------------------------------
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# ---------------------------------------------------------------------
from PIL import Image

from qai_hub_models.models._shared.stable_diffusion.app import StableDiffusionApp
from qai_hub_models.models._shared.stable_diffusion.model import (
    StableDiffusionQuantizableBase,
)
from qai_hub_models.utils.args import (
    demo_model_components_from_cli_args,
    get_on_device_demo_parser,
    validate_on_device_demo_args,
)
from qai_hub_models.utils.base_model import CollectionModel, TargetRuntime
from qai_hub_models.utils.display import display_or_save_image, to_uint8

DEFAULT_PROMPT = "Painting - She Danced By The Light Of The Moon by Steve Henderson"


# Run Stable Diffuison end-to-end on a given prompt. The demo will output an
# AI-generated image based on the description in the prompt.
def stable_diffusion_demo(
    model_id: str, model_cls: type[CollectionModel], is_test: bool = False
):
    parser = get_on_device_demo_parser(
        available_target_runtimes=[TargetRuntime.QNN],
        default_device="Snapdragon X Elite CRD",
        add_output_dir=True,
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=DEFAULT_PROMPT,
        help="Prompt for stable diffusion",
    )
    parser.add_argument(
        "--num-steps",
        type=int,
        default=5,
        help="Number of diffusion steps",
    )
    parser.add_argument(
        "--use-torch-fp32", action="store_true", help="Use torch fp32 (no AIMET)"
    )
    args = parser.parse_args([] if is_test else None)

    TextEncoderQuantizable = model_cls.component_classes[0]
    UnetQuantizable = model_cls.component_classes[1]
    VaeDecoderQuantizable = model_cls.component_classes[2]
    validate_on_device_demo_args(args, model_id)

    if args.use_torch_fp32:
        text_encoder = TextEncoderQuantizable.make_torch_model()  # type: ignore
        unet = UnetQuantizable.make_torch_model()  # type: ignore
        vae_decoder = VaeDecoderQuantizable.make_torch_model()  # type: ignore
    else:
        text_encoder, unet, vae_decoder = demo_model_components_from_cli_args(
            model_cls, model_id, args
        )

    assert issubclass(model_cls, StableDiffusionQuantizableBase)
    tokenizer = model_cls.make_tokenizer()
    scheduler = model_cls.make_scheduler()
    time_embedding = model_cls.make_time_embedding_hf()

    app = StableDiffusionApp(
        text_encoder=text_encoder,
        vae_decoder=vae_decoder,
        unet=unet,
        tokenizer=tokenizer,
        scheduler=scheduler,
        time_embedding=time_embedding,
        # OnDeviceModel account for channel_last already
        channel_last_latent=False,
    )

    image = app.generate_image(
        args.prompt,
        num_steps=args.num_steps,
    )

    pil_img = Image.fromarray(to_uint8(image.detach().cpu().numpy())[0])

    if args.use_torch_fp32:
        default_output_dir = "export/torch_fp32"
    elif args.on_device:
        default_output_dir = "export/on_device_e2e"
    else:
        default_output_dir = "export/quantsim"
    output_dir = args.output_dir or default_output_dir
    if not is_test:
        display_or_save_image(pil_img, output_dir)
