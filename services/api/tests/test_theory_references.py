"""Teacher examples must not be an exhaustive vocabulary or override a meaning check."""

from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.teaching.grounded import GroundedSpeaker
from test_brain2 import small_index
from test_grounded import loop_at_theory


def test_matching_example_does_not_skip_semantic_check_for_a_contradiction():
    provider = FakeChatModel([{"ideas": []}])
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=provider), allow_knowledge=True)
    loop, first = loop_at_theory(speaker)
    variant = next(t for t in loop.chapter.node(first.node_id).theory if t.ask == first.prompt)
    said = f"Không phải {variant.accept[0]}, con cho rằng kết quả khác."
    assert loop._accepts(variant, said)
    assert loop._theory_by_meaning(variant, said, None) is False
    assert len(provider.calls) == 1


def test_short_paraphrase_is_read_even_without_a_configured_phrase_list():
    provider = FakeChatModel([{"ideas": [{"idea": 0, "quote": "bốn phần"}]}])
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=provider), allow_knowledge=True)
    loop, first = loop_at_theory(speaker)
    variant = loop.chapter.node(first.node_id).theory[0].model_copy(update={"accept": []})
    assert loop._theory_by_meaning(variant, "bốn phần", None) is True
    assert len(provider.calls) == 1
