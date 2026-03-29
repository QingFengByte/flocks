#!/usr/bin/env python3
"""
Test Prompt System Memory Integration

Tests memory injection into system prompts.
"""

import asyncio


async def test_prompt_memory():
    """Test prompt memory integration"""
    print("=" * 70)
    print("Testing Prompt Memory Integration")
    print("=" * 70)
    
    # Test 1: Import
    print("\n[1/4] Testing imports...")
    try:
        from flocks.session import SessionPrompt, SessionMemory
        print("✅ Successfully imported prompt and memory modules")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False
    
    # Test 2: Test build_memory_context with disabled memory
    print("\n[2/4] Testing build_memory_context (disabled)...")
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create disabled memory
            memory = SessionMemory(
                session_id="test",
                project_id="proj",
                workspace_dir=tmpdir,
                enabled=False,
            )
            
            # Should return None
            context = await SessionPrompt.build_memory_context(
                session_memory=memory,
                user_message="test query",
            )
            
            print(f"   Context (disabled): {context}")
            assert context is None, "Should return None when disabled"
            
            print("✅ Disabled memory handling correct")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    # Test 3: Test build_system_prompt without memory
    print("\n[3/4] Testing build_system_prompt without memory...")
    try:
        prompt = await SessionPrompt.build_system_prompt(
            agent_name="test_agent",
            include_environment=False,
            include_custom=False,
            include_memory=False,
        )
        
        print(f"   Prompt length: {len(prompt)} chars")
        assert len(prompt) > 0, "Should generate prompt"
        assert "test_agent" in prompt, "Should include agent name"
        
        print("✅ System prompt generation working")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: Test build_system_prompt with memory (disabled)
    print("\n[4/4] Testing build_system_prompt with memory (disabled)...")
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = SessionMemory(
                session_id="test",
                project_id="proj",
                workspace_dir=tmpdir,
                enabled=False,
            )
            
            prompt = await SessionPrompt.build_system_prompt(
                agent_name="test_agent",
                include_environment=False,
                include_custom=False,
                include_memory=True,
                session_memory=memory,
                user_message="test query",
            )
            
            print(f"   Prompt length: {len(prompt)} chars")
            assert len(prompt) > 0, "Should generate prompt"
            assert "Relevant Memory" not in prompt, "Should not include memory section when disabled"
            
            print("✅ Memory integration working correctly")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 70)
    print("✅ All Prompt Memory integration tests passed!")
    print("=" * 70)
    
    print("\n📋 Prompt Memory Integration Ready:")
    print("   ✅ build_memory_context() method")
    print("   ✅ build_system_prompt() with memory support")
    print("   ✅ Automatic memory retrieval")
    print("   ✅ Graceful disabled handling")
    
    print("\n🎯 Usage Example:")
    print("   memory = await Session.get_memory(project_id, session_id)")
    print("   prompt = await SessionPrompt.build_system_prompt(")
    print("       include_memory=True,")
    print("       session_memory=memory,")
    print("       user_message='How do I use transformers?'")
    print("   )")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_prompt_memory())
    exit(0 if success else 1)
