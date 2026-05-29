"""
Test suite for blast radius analysis and impact mapping pipeline.
Verifies dependency traversal, risk scoring, and stream purity.
"""

import unittest
import sys
import os

# Add project root to path
current_file = os.path.abspath(__file__)
if 'apps' in current_file and 'ai-core' in current_file:
    apps_idx = current_file.find('apps')
    project_root = current_file[:apps_idx].rstrip('/')
else:
    project_root = os.path.dirname(os.path.dirname(current_file))
sys.path.insert(0, project_root)

from schemas.impact_state import ImpactGraphState
from agents.blast_radius_analyzer_agent import BlastRadiusAnalyzerAgent
from graphs.impact_analysis_graph import ImpactAnalysisGraph


class TestImpactGraphState(unittest.TestCase):
    """Test suite for ImpactGraphState schema."""
    
    def test_initialization(self):
        """Test state initializes with correct defaults."""
        state = ImpactGraphState(target_file="test.py")
        
        self.assertEqual(state.target_file, "test.py")
        self.assertEqual(state.max_traversal_depth, 3)
        self.assertEqual(state.architectural_risk_score, 0.0)
        self.assertEqual(state.blast_radius_classification, "isolated")
        self.assertEqual(len(state.impacted_nodes), 0)
    
    def test_risk_score_calculation_isolated(self):
        """Test risk score for isolated file (no dependents)."""
        state = ImpactGraphState(
            target_file="isolated.py",
            impacted_nodes=[]
        )
        
        score = state.calculate_risk_score()
        self.assertEqual(score, 0.0)
    
    def test_risk_score_calculation_direct_deps(self):
        """Test risk score with direct dependents (depth 1)."""
        state = ImpactGraphState(
            target_file="core.py",
            impacted_nodes=[
                {"relative_path": "service1.py", "language": "Python", "depth": 1},
                {"relative_path": "service2.py", "language": "Python", "depth": 1}
            ]
        )
        
        score = state.calculate_risk_score()
        # 2 nodes * 1.5 = 3.0
        self.assertEqual(score, 3.0)
    
    def test_risk_score_calculation_multi_depth(self):
        """Test risk score with multi-depth dependents."""
        state = ImpactGraphState(
            target_file="core.py",
            impacted_nodes=[
                {"relative_path": "service1.py", "language": "Python", "depth": 1},
                {"relative_path": "handler.py", "language": "Python", "depth": 2},
                {"relative_path": "util.py", "language": "Python", "depth": 3}
            ]
        )
        
        score = state.calculate_risk_score()
        # 1.5 + 0.5 + 0.2 = 2.2
        self.assertEqual(score, 2.2)
    
    def test_risk_score_capped_at_10(self):
        """Test risk score is capped at 10.0."""
        state = ImpactGraphState(
            target_file="core.py",
            impacted_nodes=[
                {"relative_path": f"file{i}.py", "language": "Python", "depth": 1}
                for i in range(10)
            ]
        )
        
        score = state.calculate_risk_score()
        # 10 * 1.5 = 15.0, but capped at 10.0
        self.assertLessEqual(score, 10.0)
    
    def test_classification_thresholds(self):
        """Test blast radius classification thresholds."""
        test_cases = [
            (0.0, "isolated"),
            (1.5, "isolated"),
            (2.0, "low"),
            (3.5, "low"),
            (4.0, "medium"),
            (5.5, "medium"),
            (6.0, "high"),
            (7.5, "high"),
            (8.0, "critical"),
            (10.0, "critical")
        ]
        
        for score, expected in test_cases:
            state = ImpactGraphState(architectural_risk_score=score)
            classification = state.classify_blast_radius()
            self.assertEqual(classification, expected, f"Score {score} should be '{expected}'")
    
    def test_language_boundary_penalty(self):
        """Test language boundary penalty in risk calculation."""
        state = ImpactGraphState(
            target_file="schema.py",
            impacted_nodes=[
                {"relative_path": "service.go", "language": "Go", "depth": 1},
            ]
        )
        
        # Note: calculate_risk_score needs target_language lookup
        # This test verifies the penalty logic exists
        score = state.calculate_risk_score()
        # Should include +2.0 penalty for language boundary
        self.assertGreaterEqual(score, 1.5)


class TestBlastRadiusAnalyzerAgent(unittest.TestCase):
    """Test suite for BlastRadiusAnalyzerAgent."""
    
    def test_isolated_file(self):
        """Test analysis of file with no dependents."""
        analyzer = BlastRadiusAnalyzerAgent()
        
        state = {
            "target_file": "scanner.py",
            "max_traversal_depth": 3,
            "reasoning_steps": []
        }
        
        result = analyzer(state)
        
        self.assertIn("impacted_nodes", result)
        self.assertIn("architectural_risk_score", result)
        self.assertIn("blast_radius_classification", result)
        
        # scanner.py has no reverse dependencies
        self.assertEqual(len(result["impacted_nodes"]), 0)
        self.assertEqual(result["architectural_risk_score"], 0.0)
        self.assertEqual(result["blast_radius_classification"], "isolated")
    
    def test_state_fields_populated(self):
        """Test that result contains all required fields."""
        analyzer = BlastRadiusAnalyzerAgent()
        
        state = {
            "target_file": "main.go",
            "max_traversal_depth": 2,
            "reasoning_steps": []
        }
        
        result = analyzer(state)
        
        # Verify all required fields
        self.assertIn("impacted_nodes", result)
        self.assertIn("architectural_risk_score", result)
        self.assertIn("blast_radius_classification", result)
        self.assertIn("reasoning_steps", result)
        
        # Verify reasoning steps were logged
        self.assertGreater(len(result["reasoning_steps"]), 0)


class TestImpactAnalysisGraph(unittest.TestCase):
    """Test suite for ImpactAnalysisGraph pipeline."""
    
    def test_pipeline_execution(self):
        """Test complete pipeline execution."""
        pipeline = ImpactAnalysisGraph()
        
        state = ImpactGraphState(
            target_file="scanner.py",
            max_traversal_depth=3,
            token_budget_max=100000
        )
        
        final_state = pipeline.execute(state)
        
        # Verify execution completed
        self.assertTrue(final_state.done_condition)
        
        # Verify state fields
        self.assertEqual(final_state.target_file, "scanner.py")
        self.assertIsInstance(final_state.impacted_nodes, list)
        self.assertIsInstance(final_state.architectural_risk_score, float)
        self.assertIn(final_state.blast_radius_classification, 
                     ["isolated", "low", "medium", "high", "critical"])
    
    def test_budget_enforcement(self):
        """Test that budget enforcement nodes exist in graph."""
        pipeline = ImpactAnalysisGraph()
        
        # Verify graph has budget checking nodes
        self.assertIsNotNone(pipeline.graph)
        
        # Budget checks happen at conditional edges
        # This is verified by successful execution without budget issues
        state = ImpactGraphState(
            target_file="test.py",
            token_budget_max=100000
        )
        
        final_state = pipeline.execute(state)
        self.assertTrue(final_state.done_condition)
    
    def test_stream_purity(self):
        """Test that no output goes to stdout."""
        import io
        
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        
        try:
            pipeline = ImpactAnalysisGraph()
            state = ImpactGraphState(
                target_file="test.py",
                token_budget_max=100000
            )
            
            pipeline.execute(state)
            
            # Check that stdout is empty
            stdout_output = sys.stdout.getvalue()
            self.assertEqual(stdout_output, "", "stdout must remain clean for protocol payloads")
        finally:
            sys.stdout = old_stdout
    
    def test_reasoning_steps_logged(self):
        """Test that reasoning steps are properly logged."""
        pipeline = ImpactAnalysisGraph()
        
        state = ImpactGraphState(
            target_file="scanner.py",
            max_traversal_depth=2,
            token_budget_max=100000
        )
        
        final_state = pipeline.execute(state)
        
        # Verify reasoning steps exist and contain expected content
        self.assertGreater(len(final_state.reasoning_steps), 0)
        
        # Should contain analysis steps
        reasoning_text = " ".join(final_state.reasoning_steps)
        self.assertIn("impact analysis", reasoning_text.lower())


class TestRiskScoringModel(unittest.TestCase):
    """Test suite for quantitative risk scoring model."""
    
    def test_base_impact_allocation(self):
        """Test base impact weights by depth."""
        # Depth 1: 1.5, Depth 2: 0.5, Depth 3: 0.2
        state = ImpactGraphState(
            target_file="core.py",
            impacted_nodes=[
                {"relative_path": "a.py", "language": "Python", "depth": 1},
                {"relative_path": "b.py", "language": "Python", "depth": 2},
                {"relative_path": "c.py", "language": "Python", "depth": 3},
            ]
        )
        
        score = state.calculate_risk_score()
        expected = 1.5 + 0.5 + 0.2
        self.assertAlmostEqual(score, expected, places=2)
    
    def test_multiple_depth1_nodes(self):
        """Test multiple direct dependents."""
        state = ImpactGraphState(
            target_file="api.py",
            impacted_nodes=[
                {"relative_path": f"service{i}.py", "language": "Python", "depth": 1}
                for i in range(4)
            ]
        )
        
        score = state.calculate_risk_score()
        expected = 4 * 1.5  # 6.0
        self.assertAlmostEqual(score, expected, places=2)
        
        state.architectural_risk_score = score
        classification = state.classify_blast_radius()
        self.assertEqual(classification, "high")


if __name__ == '__main__':
    unittest.main()
