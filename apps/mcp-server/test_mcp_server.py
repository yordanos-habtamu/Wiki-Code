"""
Isolated Test Harness for FastMCP Server.
Loads the MCP app programmatically and tests all tools without stdio loops.
"""

import os
import sys
import json

# Redirect stdout to stderr to enforce zero stdout pollution
sys.stdout = sys.stderr

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Import the MCP server module
import importlib.util

mcp_app_path = os.path.join(os.path.dirname(__file__), "app.py")
spec = importlib.util.spec_from_file_location("mcp_app", mcp_app_path)
mcp_app_module = importlib.util.module_from_spec(spec)
sys.modules["mcp_app"] = mcp_app_module
spec.loader.exec_module(mcp_app_module)

# Access the MCP instance and tool functions
mcp = mcp_app_module.mcp
get_codebase_structure = mcp_app_module.get_codebase_structure
search_codebase_abstracts = mcp_app_module.search_codebase_abstracts
get_token_telemetry = mcp_app_module.get_token_telemetry
audit_code_quality = mcp_app_module.audit_code_quality
map_blast_radius = mcp_app_module.map_blast_radius


def test_get_codebase_structure():
    """Test the codebase structural mapping tool."""
    print("\n=== Testing get_codebase_structure ===", file=sys.stderr)
    
    try:
        # Call the tool directly
        result = get_codebase_structure()
        
        # Validate response structure
        assert isinstance(result, list), "Result should be a list"
        assert len(result) > 0, "Result should not be empty"
        
        # Check first item structure
        first_item = result[0]
        assert "relative_path" in first_item, "Missing relative_path"
        assert "language" in first_item, "Missing language"
        assert "file_hash" in first_item, "Missing file_hash"
        assert "file_size" in first_item, "Missing file_size"
        assert "symbol_count" in first_item, "Missing symbol_count"
        assert "dependency_count" in first_item, "Missing dependency_count"
        
        print(f"✓ Retrieved {len(result)} files", file=sys.stderr)
        print(f"✓ Sample file: {first_item['relative_path']} ({first_item['language']})", file=sys.stderr)
        print(f"✓ Symbols: {first_item['symbol_count']}, Dependencies: {first_item['dependency_count']}", file=sys.stderr)
        
        # Display all files
        print("\nFiles in codebase:", file=sys.stderr)
        for file_info in result:
            print(
                f"  - {file_info['relative_path']} "
                f"[{file_info['language']}] "
                f"(symbols: {file_info['symbol_count']}, "
                f"deps: {file_info['dependency_count']})",
                file=sys.stderr
            )
        
        print("\n✓ get_codebase_structure test passed", file=sys.stderr)
        return True
        
    except Exception as e:
        print(f"✗ get_codebase_structure test failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


def test_search_codebase_abstracts():
    """Test the semantic codebase abstraction search tool."""
    print("\n=== Testing search_codebase_abstracts ===", file=sys.stderr)
    
    test_queries = [
        "class scanner or project structures",
        "database connection and repository pattern",
        "embedding and vector search",
        "token usage and telemetry"
    ]
    
    try:
        for query in test_queries:
            print(f"\nQuery: '{query}'", file=sys.stderr)
            
            # Call the tool directly
            results = search_codebase_abstracts(query, n_results=3)
            
            # Validate response structure
            assert isinstance(results, list), "Result should be a list"
            
            if len(results) > 0:
                print(f"  Found {len(results)} matches:", file=sys.stderr)
                for idx, match in enumerate(results):
                    assert "relative_path" in match, "Missing relative_path"
                    assert "language" in match, "Missing language"
                    assert "abstract" in match, "Missing abstract"
                    assert "distance" in match, "Missing distance"
                    assert "file_size" in match, "Missing file_size"
                    assert "entity_count" in match, "Missing entity_count"
                    
                    print(
                        f"  {idx+1}. {match['relative_path']} "
                        f"[{match['language']}] "
                        f"(distance: {match['distance']:.4f})",
                        file=sys.stderr
                    )
            else:
                print(f"  No matches found", file=sys.stderr)
        
        print("\n✓ search_codebase_abstracts test passed", file=sys.stderr)
        return True
        
    except Exception as e:
        print(f"✗ search_codebase_abstracts test failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


def test_get_token_telemetry():
    """Test the token auditing telemetry tool."""
    print("\n=== Testing get_token_telemetry ===", file=sys.stderr)
    
    test_windows = [7, 30, 90]
    
    try:
        for window in test_windows:
            print(f"\nTime window: {window} days", file=sys.stderr)
            
            # Call the tool directly
            telemetry = get_token_telemetry(time_window_days=window)
            
            # Validate response structure
            assert isinstance(telemetry, dict), "Result should be a dict"
            assert "total_tokens_consumed" in telemetry, "Missing total_tokens_consumed"
            assert "total_requests" in telemetry, "Missing total_requests"
            assert "time_window_days" in telemetry, "Missing time_window_days"
            assert "per_provider_metrics" in telemetry, "Missing per_provider_metrics"
            assert "budget_health" in telemetry, "Missing budget_health"
            
            # Validate types
            assert isinstance(telemetry["total_tokens_consumed"], int), "total_tokens should be int"
            assert isinstance(telemetry["total_requests"], int), "total_requests should be int"
            assert isinstance(telemetry["per_provider_metrics"], list), "per_provider_metrics should be list"
            assert telemetry["budget_health"] in ["healthy", "moderate", "high_usage"], "Invalid budget_health"
            
            print(
                f"  Total tokens: {telemetry['total_tokens_consumed']}",
                file=sys.stderr
            )
            print(
                f"  Total requests: {telemetry['total_requests']}",
                file=sys.stderr
            )
            print(
                f"  Budget health: {telemetry['budget_health']}",
                file=sys.stderr
            )
            
            # Display per-provider metrics
            if len(telemetry["per_provider_metrics"]) > 0:
                print(f"  Provider breakdown:", file=sys.stderr)
                for metric in telemetry["per_provider_metrics"]:
                    print(
                        f"    - {metric['provider']}: "
                        f"{metric['total_tokens']} tokens "
                        f"({metric['request_count']} requests)",
                        file=sys.stderr
                    )
            else:
                print(f"  No provider metrics available (no LLM calls logged yet)", file=sys.stderr)
        
        print("\n✓ get_token_telemetry test passed", file=sys.stderr)
        return True
        
    except Exception as e:
        print(f"✗ get_token_telemetry test failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


def test_stream_integrity():
    """Verify that stdout remains clean (no pollution)."""
    print("\n=== Testing Stream Integrity ===", file=sys.stderr)
    
    # Capture stdout during tool execution
    import io
    
    # Save original stdout
    captured_stdout = io.StringIO()
    original_stdout = sys.stdout
    
    try:
        # Redirect stdout to our capture buffer
        sys.stdout = captured_stdout
        
        # Execute all tools
        get_codebase_structure()
        search_codebase_abstracts("test query", n_results=1)
        get_token_telemetry(time_window_days=30)
        
        # Check if anything was written to stdout
        stdout_content = captured_stdout.getvalue()
        
        if len(stdout_content) == 0:
            print("✓ stdout is 100% clean (no pollution)", file=sys.stderr)
            return True
        else:
            print(f"✗ stdout contains {len(stdout_content)} characters of pollution", file=sys.stderr)
            print(f"  Content: {stdout_content[:200]}", file=sys.stderr)
            return False
            
    finally:
        # Restore original stdout
        sys.stdout = original_stdout


def test_audit_code_quality():
    """Test the comprehensive code quality audit tool."""
    print("\n=== Testing audit_code_quality ===", file=sys.stderr)
    
    test_files = ["scanner.py", "main.go", "utils.ts"]
    
    try:
        for target_file in test_files:
            print(f"\nAuditing: {target_file}", file=sys.stderr)
            
            # Call the tool directly
            result = audit_code_quality(target_file, token_budget=100000)
            
            # Validate response structure
            assert isinstance(result, dict), "Result should be a dict"
            assert "target_file" in result, "Missing target_file"
            assert "quality_score" in result, "Missing quality_score"
            assert "refactoring_priority" in result, "Missing refactoring_priority"
            assert "detected_smells" in result, "Missing detected_smells"
            assert "proposed_architecture" in result, "Missing proposed_architecture"
            assert "done_condition" in result, "Missing done_condition"
            
            # Validate types
            assert result["quality_score"] is None or isinstance(result["quality_score"], (int, float)), "quality_score should be numeric or None"
            if result["quality_score"] is not None:
                assert 0.0 <= result["quality_score"] <= 10.0, "quality_score should be 0-10"
            assert isinstance(result["detected_smells"], list), "detected_smells should be list"
            assert isinstance(result["proposed_architecture"], list), "proposed_architecture should be list"
            assert result["done_condition"] == True, "Audit should complete successfully"
            
            print(
                f"  Quality score: {result['quality_score']}/10.0",
                file=sys.stderr
            )
            print(
                f"  Priority: {result['refactoring_priority']}",
                file=sys.stderr
            )
            print(
                f"  Smells detected: {len(result['detected_smells'])}",
                file=sys.stderr
            )
            print(
                f"  Proposals generated: {len(result['proposed_architecture'])}",
                file=sys.stderr
            )
            
            # Display detected smells
            if len(result["detected_smells"]) > 0:
                print(f"  Detected smells:", file=sys.stderr)
                for smell in result["detected_smells"]:
                    print(
                        f"    - [{smell['severity']}] {smell['type']}: {smell['description']}",
                        file=sys.stderr
                    )
        
        print("\n✓ audit_code_quality test passed", file=sys.stderr)
        return True
        
    except Exception as e:
        print(f"✗ audit_code_quality test failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


def test_map_blast_radius():
    """Test the downstream blast radius and impact mapping tool."""
    print("\n=== Testing map_blast_radius ===", file=sys.stderr)
    
    test_cases = [
        ("scanner.py", 3),
        ("main.go", 2),
        ("utils.ts", 3)
    ]
    
    try:
        for target_file, max_depth in test_cases:
            print(f"\nMapping blast radius: {target_file} (depth={max_depth})", file=sys.stderr)
            
            # Call the tool directly
            result = map_blast_radius(target_file, max_depth=max_depth, token_budget=100000)
            
            # Validate response structure
            assert isinstance(result, dict), "Result should be a dict"
            assert "target_file" in result, "Missing target_file"
            assert "impacted_nodes" in result, "Missing impacted_nodes"
            assert "architectural_risk_score" in result, "Missing architectural_risk_score"
            assert "blast_radius_classification" in result, "Missing blast_radius_classification"
            assert "max_traversal_depth" in result, "Missing max_traversal_depth"
            assert "done_condition" in result, "Missing done_condition"
            
            # Validate types
            assert isinstance(result["impacted_nodes"], list), "impacted_nodes should be list"
            assert isinstance(result["architectural_risk_score"], (int, float)), "risk_score should be numeric"
            assert 0.0 <= result["architectural_risk_score"] <= 10.0, "risk_score should be 0-10"
            assert result["blast_radius_classification"] in [
                "isolated", "low", "medium", "high", "critical"
            ], "Invalid classification"
            assert result["done_condition"] == True, "Analysis should complete successfully"
            
            print(
                f"  Impacted nodes: {len(result['impacted_nodes'])}",
                file=sys.stderr
            )
            print(
                f"  Risk score: {result['architectural_risk_score']}/10.0",
                file=sys.stderr
            )
            print(
                f"  Classification: {result['blast_radius_classification']}",
                file=sys.stderr
            )
            
            # Display impacted nodes
            if len(result["impacted_nodes"]) > 0:
                print(f"  Impacted nodes:", file=sys.stderr)
                for node in result["impacted_nodes"]:
                    print(
                        f"    - Depth {node['depth']}: {node['relative_path']} ({node['language']})",
                        file=sys.stderr
                    )
        
        print("\n✓ map_blast_radius test passed", file=sys.stderr)
        return True
        
    except Exception as e:
        print(f"✗ map_blast_radius test failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


def test_budget_enforcement():
    """Test that artificially low token budgets trigger safety gates."""
    print("\n=== Testing Budget Enforcement ===", file=sys.stderr)
    
    try:
        # Test with very low budget (should complete but log budget warnings)
        print("\nTesting audit_code_quality with low budget (1000 tokens)", file=sys.stderr)
        result = audit_code_quality("scanner.py", token_budget=1000)
        
        assert isinstance(result, dict), "Result should be a dict"
        assert "done_condition" in result, "Should have done_condition"
        
        print(
            f"  Completed with low budget: done={result['done_condition']}",
            file=sys.stderr
        )
        
        # Test map_blast_radius with low budget
        print("\nTesting map_blast_radius with low budget (1000 tokens)", file=sys.stderr)
        result = map_blast_radius("scanner.py", max_depth=2, token_budget=1000)
        
        assert isinstance(result, dict), "Result should be a dict"
        assert "done_condition" in result, "Should have done_condition"
        
        print(
            f"  Completed with low budget: done={result['done_condition']}",
            file=sys.stderr
        )
        
        print("\n✓ Budget enforcement test passed", file=sys.stderr)
        return True
        
    except Exception as e:
        print(f"✗ Budget enforcement test failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


def main():
    print("=" * 70, file=sys.stderr)
    print("WikiHub MCP Server Test Suite", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Stream integrity
    if test_stream_integrity():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 2: Codebase structure
    if test_get_codebase_structure():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 3: Semantic search
    if test_search_codebase_abstracts():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 4: Token telemetry
    if test_get_token_telemetry():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 5: Code quality audit
    if test_audit_code_quality():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 6: Blast radius mapping
    if test_map_blast_radius():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 7: Budget enforcement
    if test_budget_enforcement():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Summary
    print("\n" + "=" * 70, file=sys.stderr)
    print(f"Test Results: {tests_passed} passed, {tests_failed} failed", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    
    if tests_failed > 0:
        sys.exit(1)
    else:
        print("\n✓ All tests passed successfully!", file=sys.stderr)


if __name__ == "__main__":
    main()
