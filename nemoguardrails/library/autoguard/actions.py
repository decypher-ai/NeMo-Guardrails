# SPDX-FileCopyrightText: Copyright (c) 2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional

import aiohttp

from nemoguardrails.actions import action
from nemoguardrails.llm.taskmanager import LLMTaskManager

log = logging.getLogger(__name__)

GUARDRAIL_RESPONSE_TEXT = {
    "confidential_detection": "Confidential Information violation",
    "gender_bias_detection": "Gender bias in text",
    "harm_detection": "Harm to human violation",
    "text_toxicity_extraction": "Toxicity in text",
    "tonal_detection": "Negative tone in text",
    "racial_bias_detection": "Racial bias in text",
    "jailbreak_detection": "Jailbreak attempt",
    "factcheck": "Factcheck violation in text",
}

DEFAULT_CONFIG = {
    "pii_fast": {
        "mode": "OFF",
        "mask": True,
        "enabled_types": [
            "[PERSON NAME]",
            "[LOCATION]",
            "[DATE OF BIRTH]",
            "[DATE]",
            "[PHONE NUMBER]",
            "[EMAIL ADDRESS]",
            "[CREDIT CARD NUMBER]",
            "[BANK ACCOUNT NUMBER]",
            "[SOCIAL SECURITY NUMBER]",
            "[MONEY]",
            "[PROFESSION]",
            "[RACE/ETHNICITY]",
            "[ORGANIZATION]",
            "[USERNAME]",
            "[PASSWORD]",
            "[IP ADDRESS]",
            "[PASSPORT NUMBER]",
            "[DRIVER LICENSE NUMBER]",
            "[SECRET_KEY]",
            "[TRANSACTION_ID]",
            "[RELIGION]",
        ],
    },
    "confidential_detection": {"mode": "OFF"},
    "gender_bias_detection": {"mode": "OFF"},
    "harm_detection": {"mode": "OFF"},
    "text_toxicity_extraction": {"mode": "OFF"},
    "racial_bias_detection": {"mode": "OFF"},
    "tonal_detection": {"mode": "OFF"},
    "jailbreak_detection": {"mode": "OFF"},
    "intellectual_property": {"mode": "OFF"},
}


async def autoguard_infer(
    request_url: str,
    text: str,
    tasks: List[str],
    matching_scores: Dict[str, Dict[str, float]],
    task_config: Optional[Dict[Any, Any]] = None,
):
    api_key = os.environ.get("AUTOGUARD_API_KEY")
    if api_key is None:
        raise ValueError("AUTOGUARD_API_KEY environment variable not set.")

    headers = {"x-api-key": api_key}
    config = DEFAULT_CONFIG
    # enable the select guardrail
    for task in tasks:
        if task not in ["text_toxicity_extraction", "pii_fast", "factcheck"]:
            config[task] = {"mode": "DETECT"}
            if matching_scores:
                config[task]["matching_scores"] = matching_scores.get(task, {})
        if task_config:
            config[task].update(task_config)
    request_body = {"prompt": text, "config": config}

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url=request_url,
            headers=headers,
            json=request_body,
        ) as response:
            if response.status != 200:
                raise ValueError(
                    f"AutoGuard call failed with status code {response.status}.\n"
                    f"Details: {await response.text()}"
                )
            async for line in response.content:
                line_text = line.strip()
                if len(line_text) > 0:
                    resp = json.loads(line_text)
                    if resp["guarded"]:
                        return True, GUARDRAIL_RESPONSE_TEXT[resp["task"]]
    return False, None


async def autoguard_toxicity_infer(
    request_url: str,
    text: str,
    matching_scores: Dict[str, Dict[str, float]],
    task_config: Optional[Dict[Any, Any]] = None,
):
    api_key = os.environ.get("AUTOGUARD_API_KEY")
    if api_key is None:
        raise ValueError("AUTOGUARD_API_KEY environment variable not set.")

    headers = {"x-api-key": api_key}
    config = DEFAULT_CONFIG
    # enable the select guardrail
    config["text_toxicity_extraction"] = {"mode": "DETECT"}
    if task_config:
        config["text_toxicity_extraction"].update(task_config)
    if matching_scores:
        config["text_toxicity_extraction"]["matching_scores"] = matching_scores.get(
            "text_toxicity_extraction", {}
        )

    request_body = {"prompt": text, "config": config}

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url=request_url,
            headers=headers,
            json=request_body,
        ) as response:
            if response.status != 200:
                raise ValueError(
                    f"AutoGuard call failed with status code {response.status}.\n"
                    f"Details: {await response.text()}"
                )
            async for line in response.content:
                line_text = line.strip()
                if len(line_text) > 0:
                    resp = json.loads(line_text)
                    if resp["task"] == "text_toxicity_extraction":
                        return (
                            resp["guarded"],
                            GUARDRAIL_RESPONSE_TEXT[resp["task"]],
                            " ".join(resp["output_data"]),
                        )
    return False, None


async def autoguard_pii_infer(
    request_url: str,
    text: str,
    entities: List[str],
    contextual_rules: List[List[str]],
    matching_scores: Dict[str, Dict[str, float]],
    task_config: Optional[Dict[Any, Any]] = None,
):
    api_key = os.environ.get("AUTOGUARD_API_KEY")
    if api_key is None:
        raise ValueError("AUTOGUARD_API_KEY environment variable not set.")

    headers = {"x-api-key": api_key}
    config = DEFAULT_CONFIG
    # enable the select guardrail
    config["pii_fast"] = {"mode": "DETECT"}
    if task_config:
        config["pii_fast"].update(task_config)

    config["pii_fast"]["enabled_types"] = entities
    config["pii_fast"]["contextual_rules"] = contextual_rules
    if matching_scores:
        config["pii_fast"]["matching_scores"] = matching_scores.get("pii_fast", {})
    request_body = {"prompt": text, "config": config}

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url=request_url,
            headers=headers,
            json=request_body,
        ) as response:
            if response.status != 200:
                raise ValueError(
                    f"AutoGuard call failed with status code {response.status}.\n"
                    f"Details: {await response.text()}"
                )
            async for line in response.content:
                line_text = line.strip()
                if len(line_text) > 0:
                    resp = json.loads(line_text)
                    if resp["task"] == "pii_fast":
                        return resp["guarded"], resp["response"]
    return False, None


async def autoguard_factcheck_infer(
    request_url: str,
    text: str,
    documents: List[str],
    matching_scores: Dict[str, Dict[str, float]],
):
    api_key = os.environ.get("AUTOGUARD_API_KEY")
    if api_key is None:
        raise ValueError("AUTOGUARD_API_KEY environment variable not set.")
    headers = {"x-api-key": api_key}
    request_body = {
        "prompt": text,
        "documents": documents,
        "matching_scores": matching_scores.get("factcheck", {}),
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url=request_url,
            headers=headers,
            json=request_body,
        ) as response:
            if response.status != 200:
                raise ValueError(
                    f"AutoGuard call failed with status code {response.status}.\n"
                    f"Details: {await response.text()}"
                )
            async for line in response.content:
                resp = json.loads(line)
                if resp["task"] == "factcheck":
                    return float(resp["response"][17:])
    return 1.0


@action()
async def autoguard_input_api(
    llm_task_manager: LLMTaskManager, context: Optional[dict] = None
):
    user_message = context.get("user_message")
    autoguard_config = llm_task_manager.config.rails.config.autoguard

    autoguard_api_url = autoguard_config.parameters.get("endpoint")
    if not autoguard_api_url:
        raise ValueError("Provide the autoguard endpoint in the config")
    tasks = getattr(autoguard_config.input, "guardrails")
    matching_scores = getattr(autoguard_config, "matching_scores", {})
    if not tasks:
        raise ValueError("Provide the guardrails in the config")
    prompt = user_message

    return await autoguard_infer(autoguard_api_url, prompt, tasks, matching_scores)


@action()
async def autoguard_pii_api(
    llm_task_manager: LLMTaskManager, context: Optional[dict] = None
):
    user_message = context.get("user_message")
    autoguard_config = llm_task_manager.config.rails.config.autoguard

    autoguard_api_url = autoguard_config.parameters.get("endpoint")
    if not autoguard_api_url:
        raise ValueError("Provide the autoguard endpoint in the config")

    entities = getattr(autoguard_config, "entities", [])
    contextual_rules = getattr(autoguard_config, "contextual_rules", [])
    matching_scores = getattr(autoguard_config, "matching_scores", {})
    return await autoguard_pii_infer(
        autoguard_api_url, user_message, entities, contextual_rules, matching_scores
    )


@action()
async def autoguard_output_api(
    llm_task_manager: LLMTaskManager, context: Optional[dict] = None
):
    bot_message = context.get("bot_message")
    autoguard_config = llm_task_manager.config.rails.config.autoguard
    autoguard_api_url = autoguard_config.parameters.get("endpoint")
    if not autoguard_api_url:
        raise ValueError("Provide the autoguard endpoint in the config")
    tasks = getattr(autoguard_config.input, "guardrails")
    matching_scores = getattr(autoguard_config, "matching_scores", {})
    if not tasks:
        raise ValueError("Provide the guardrails in the config")

    prompt = bot_message

    return await autoguard_infer(autoguard_api_url, prompt, tasks, matching_scores)


@action()
async def autoguard_toxicity_input_api(
    llm_task_manager: LLMTaskManager, context: Optional[dict] = None
):
    user_message = context.get("user_message")
    autoguard_config = llm_task_manager.config.rails.config.autoguard

    autoguard_toxicity_api_url = autoguard_config.parameters.get("toxicity_endpoint")
    matching_scores = getattr(autoguard_config, "matching_scores", {})
    if not autoguard_toxicity_api_url:
        raise ValueError("Provide the autoguard endpoint in the config")
    return await autoguard_toxicity_infer(
        autoguard_toxicity_api_url, user_message, matching_scores
    )


@action()
async def autoguard_toxicity_output_api(
    llm_task_manager: LLMTaskManager, context: Optional[dict] = None
):
    bot_message = context.get("bot_message")
    autoguard_config = llm_task_manager.config.rails.config.autoguard

    autoguard_toxicity_api_url = autoguard_config.parameters.get("toxicity_endpoint")
    if not autoguard_toxicity_api_url:
        raise ValueError("Provide the autoguard endpoint in the config")
    return await autoguard_toxicity_infer(autoguard_toxicity_api_url, bot_message)


@action()
async def autoguard_factcheck_api(
    llm_task_manager: LLMTaskManager, context: Optional[dict] = None
):
    api_key = os.environ.get("AUTOGUARD_API_KEY")

    if api_key is None:
        raise ValueError("AUTOGUARD_API_KEY environment variable not set.")

    bot_message = context.get("bot_message")
    documents = context.get("relevant_chunks", [])
    autoguard_config = llm_task_manager.config.rails.config.autoguard
    autoguard_fact_check_api_url = autoguard_config.parameters.get(
        "fact_check_endpoint"
    )
    if not autoguard_fact_check_api_url:
        raise ValueError("Provide the autoguard factcheck endpoint in the config")
    if isinstance(documents, str):
        documents = documents.split("\n")
    prompt = bot_message
    matching_scores = getattr(autoguard_config, "matching_scores", {})
    if isinstance(documents, list) and len(documents) > 0:
        return await autoguard_factcheck_infer(
            autoguard_fact_check_api_url, prompt, documents, matching_scores
        )
    else:
        raise ValueError("Provide relevant documents in proper format")