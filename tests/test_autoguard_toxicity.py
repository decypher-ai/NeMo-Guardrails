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

import os
from typing import Optional

import pytest

from nemoguardrails import RailsConfig
from tests.utils import TestChat

CONFIGS_FOLDER = os.path.join(os.path.dirname(__file__), ".", "test_configs")


@pytest.mark.asyncio
async def test_fact_checking_greeting():
    # Test 1 - Greeting - No fact-checking invocation should happen
    config = RailsConfig.from_path(os.path.join(CONFIGS_FOLDER, "autoguard_toxicity"))

    chat = TestChat(
        config,
        llm_completions=["  express greeting", "Hi! How can I assist today?"],
    )

    chat >> "hi"
    await chat.bot_async("Hi! How can I assist today?")


@pytest.mark.asyncio
async def test_toxic_input():
    config = RailsConfig.from_path(os.path.join(CONFIGS_FOLDER, "autoguard_toxicity"))

    chat = TestChat(
        config,
        llm_completions=[
            "  ask toxic question",
            "Or some of you shit heads could go get a job..... ",
            "Toxicity in text has been detected by AutoGuard; Sorry, can't process. Toxic phrases: shit heads",
        ],
    )

    async def mock_autoguard_toxicity_input_api(
        context: Optional[dict] = None, **kwargs
    ):
        query = context.get("user_message")
        if query == "Or some of you shit heads could go get a job..... ":
            return True, "Toxicity in text", "shit heads"
        else:
            return False, None

    chat.app.register_action(
        mock_autoguard_toxicity_input_api, "autoguard_toxicity_input_api"
    )

    chat >> "Or some of you shit heads could go get a job....."

    await chat.bot_async(
        "Toxicity in text has been detected by AutoGuard; Sorry, can't process. Toxic phrases: shit heads"
    )