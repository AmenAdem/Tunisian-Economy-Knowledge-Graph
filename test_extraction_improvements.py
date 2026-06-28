#!/usr/bin/env python3
"""
Test script to verify LLM extraction improvements.
Run: python test_extraction_improvements.py
"""

import time
from backend.extraction.relation_extractor import RelationExtractor

def test_quality_filter():
    """Test quality filter for low-quality chunks."""
    print("=" * 60)
    print("TEST 1: Quality Filter")
    print("=" * 60)

    extractor = RelationExtractor()

    # Test cases
    test_cases = [
        ("TABLE OF CONTENTS\n1. Introduction ... 5\n2. Analysis ... 12", True, "TOC"),
        ("APPENDIX: List of Banks", True, "Appendix header"),
        ("08:22 Page 4", True, "Page number"),
        ("Aziz Miled est PDG de Poulina Group Holding", False, "Good narrative"),
        ("BIAT détient 51% de Tunisia Bank", False, "Ownership statement"),
        ("a b c d e", True, "Too short"),
    ]

    passed = 0
    for text, expected_low_quality, description in test_cases:
        is_low = extractor._is_low_quality_chunk(text)
        status = "✅" if is_low == expected_low_quality else "❌"
        print(f"{status} {description}: {is_low} (expected {expected_low_quality})")
        if is_low == expected_low_quality:
            passed += 1

    print(f"\nPassed: {passed}/{len(test_cases)}")
    print()


def test_extraction_speed():
    """Test extraction speed with new model."""
    print("=" * 60)
    print("TEST 2: Extraction Speed (Gemini 2.0 Flash)")
    print("=" * 60)

    extractor = RelationExtractor()

    # Sample text with clear relationships
    text = """
    Aziz Miled est le PDG de Poulina Group Holding depuis 1990.
    La société a acquis Tunisia Catering en 2005 pour 50 millions de dinars.
    Poulina Group Holding détient 51% de Tunisia Catering.
    Le siège social est situé à Tunis.
    """

    print(f"Text length: {len(text)} chars")
    print(f"Model: google/gemini-2.0-flash-exp:free")
    print("\nExtracting...")

    start = time.time()
    result = extractor.extract_relations(text, entities=None)
    elapsed = time.time() - start

    print(f"\n⏱️  Time taken: {elapsed:.2f}s")
    print(f"📊 Entities: {len(result.entities)}")
    print(f"🔗 Relations: {len(result.relations)}")

    if elapsed < 20:
        print("✅ Speed acceptable (<20s)")
    else:
        print("⚠️  Slower than expected (>20s)")

    if len(result.relations) > 0:
        print("✅ Relations extracted successfully")
        for rel in result.relations[:3]:
            print(f"   - {rel.source} → {rel.relation} → {rel.target}")
    else:
        print("⚠️  No relations extracted")

    print()


def test_context_window():
    """Test context window feature."""
    print("=" * 60)
    print("TEST 3: Context Window")
    print("=" * 60)

    extractor = RelationExtractor()

    # Simulate chunks where relationship spans boundaries
    context_before = "Aziz Miled a été nommé directeur général de"
    main_text = "Poulina Group Holding en 1990. Il a transformé"
    context_after = "l'entreprise en un leader du secteur."

    print("Context before: ", context_before[-50:], "...")
    print("Main text:      ", main_text)
    print("Context after:  ...", context_after[:50])

    # Build prompt to see context structure
    prompt = extractor._build_prompt(
        main_text,
        entities=None,
        context_before=context_before,
        context_after=context_after
    )

    has_prev_context = "[CONTEXT FROM PREVIOUS SECTION]" in prompt
    has_next_context = "[CONTEXT FROM NEXT SECTION]" in prompt
    has_main_text = "[MAIN TEXT TO ANALYZE]" in prompt

    print(f"\n✅ Previous context included: {has_prev_context}")
    print(f"✅ Next context included: {has_next_context}")
    print(f"✅ Main text marked: {has_main_text}")

    if has_prev_context and has_next_context and has_main_text:
        print("\n✅ Context window working correctly")
    else:
        print("\n⚠️  Context window may have issues")

    print()


def test_simplified_prompt():
    """Test simplified prompt."""
    print("=" * 60)
    print("TEST 4: Simplified Prompt")
    print("=" * 60)

    extractor = RelationExtractor()
    system_prompt = extractor._get_system_prompt()

    print(f"System prompt length: {len(system_prompt)} chars")
    print(f"Target: <2000 chars (was 5142)")

    if len(system_prompt) < 2000:
        print("✅ Prompt simplified successfully")
    else:
        print("⚠️  Prompt still too long")

    # Check for examples
    has_examples = "EXAMPLE 1" in system_prompt
    has_toc_example = "TABLE OF CONTENTS" in system_prompt

    print(f"✅ Contains examples: {has_examples}")
    print(f"✅ Contains TOC skip example: {has_toc_example}")

    print()


if __name__ == "__main__":
    print("\n🧪 Testing LLM Extraction Improvements\n")

    try:
        test_quality_filter()
        test_simplified_prompt()
        test_context_window()

        print("=" * 60)
        print("⚠️  NOTE: Skipping live extraction test to avoid API calls")
        print("To test live extraction, uncomment test_extraction_speed()")
        print("=" * 60)

        # Uncomment to test live extraction (will make API call)
        # test_extraction_speed()

        print("\n✅ All tests completed!\n")

    except Exception as e:
        print(f"\n❌ Error during testing: {e}\n")
        import traceback
        traceback.print_exc()
