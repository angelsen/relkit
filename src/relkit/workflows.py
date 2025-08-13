"""Workflow builder for orchestrating complex operations."""

from typing import Callable, List, Any, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from .models import Output, Context


class Workflow:
    """Builder for multi-step workflows with checks, steps, and parallel execution."""

    def __init__(self, name: str):
        self.name = name
        self.operations: List[tuple[str, Any]] = []

    def check(self, func: Callable[[Context], Output]) -> "Workflow":
        """Add a validation check that collects failures without stopping."""
        self.operations.append(("check", func))
        return self

    def step(self, func: Callable[[Context], Output]) -> "Workflow":
        """Add a critical step that stops workflow on failure."""
        self.operations.append(("step", func))
        return self

    def parallel(self, *funcs: Callable[[Context], Output]) -> "Workflow":
        """Add parallel operations that run simultaneously."""
        self.operations.append(("parallel", funcs))
        return self

    def run(self, ctx: Context, **kwargs) -> Output:
        """Execute the workflow and return aggregated results."""
        all_checks_passed = True
        check_failures: List[str] = []
        check_details: List[Dict[str, Any]] = []
        completed_steps: List[Dict[str, Any]] = []

        for op_type, operation in self.operations:
            if op_type == "check":
                # Run check and collect result
                result = operation(ctx, **kwargs)
                if not result.success:
                    all_checks_passed = False
                    check_failures.append(result.message)
                    if result.details:
                        check_details.extend(result.details)
                else:
                    completed_steps.append(
                        {"type": "step", "name": operation.__name__, "success": True}
                    )

            elif op_type == "step":
                # Run critical step
                result = operation(ctx, **kwargs)
                if not result.success:
                    return Output(
                        success=False,
                        message=f"Workflow '{self.name}' failed at step: {operation.__name__}",
                        details=[{"type": "text", "content": result.message}]
                        + (result.details or []),
                        next_steps=result.next_steps,
                    )
                completed_steps.append(
                    {"type": "step", "name": operation.__name__, "success": True}
                )

            elif op_type == "parallel":
                # Run operations in parallel
                parallel_results = self._run_parallel(ctx, operation, **kwargs)
                failed = [r for r in parallel_results if not r.success]

                if failed:
                    all_checks_passed = False
                    for result in failed:
                        check_failures.append(result.message)
                        if result.details:
                            check_details.extend(result.details)

                for func, result in zip(operation, parallel_results):
                    if result.success:
                        completed_steps.append(
                            {"type": "step", "name": func.__name__, "success": True}
                        )

        # Return aggregated result
        if not all_checks_passed:
            # For preflight, just show summary messages
            return Output(
                success=False,
                message=f"{len(check_failures)} check(s) failed",
                details=[{"type": "text", "content": msg} for msg in check_failures],
                next_steps=[
                    "Run 'relkit check' for detailed issues",
                    "Or run specific checks:",
                    "  relkit check git",
                    "  relkit check format",
                    "  relkit check lint",
                    "  relkit check types",
                ],
            )

        return Output(
            success=True,
            message=f"Workflow '{self.name}' completed successfully",
            details=completed_steps,
        )

    def _run_parallel(self, ctx: Context, funcs: tuple, **kwargs) -> List[Output]:
        """Execute functions in parallel and return results."""
        results = []
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(func, ctx, **kwargs): func for func in funcs}

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    func = futures[future]
                    results.append(
                        Output(
                            success=False,
                            message=f"Parallel task {func.__name__} failed: {str(e)}",
                        )
                    )

        return results
