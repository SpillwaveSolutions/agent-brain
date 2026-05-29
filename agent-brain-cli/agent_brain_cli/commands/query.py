"""Query command for searching documents."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..client import ConnectionError, ServerError
from ..client.api_client import ResultExplanation
from ..client.transport import open_client
from ..diagnostics import doctor_hint_message

console = Console()


def _render_explanation(explanation: ResultExplanation) -> None:
    """Render a ResultExplanation as a sub-panel below the main result.

    Layout (only rows that have data are emitted):
        Why:      <reason string>
        Matched:  term1, term2, ...
        Fusion:   key=value | key=value | ...
        Graph:    subject -> predicate -> object
        Rerank:   moved up/down N places (if any)
        Fallback: graph -> vector
    """
    table = Table(show_header=False, box=None, padding=(0, 1), expand=False)
    table.add_column("label", style="cyan", no_wrap=True)
    table.add_column("value", style="dim")

    table.add_row("Why:", explanation.reason)

    if explanation.matched_terms:
        highlighted = Text(", ".join(explanation.matched_terms))
        highlighted.highlight_words(explanation.matched_terms, style="bold yellow")
        table.add_row("Matched:", highlighted)

    if explanation.fusion:
        parts = [f"{k}={v:.4f}" for k, v in explanation.fusion.items()]
        table.add_row("Fusion:", " | ".join(parts))

    if explanation.graph_path:
        table.add_row("Graph:", " -> ".join(explanation.graph_path))

    if explanation.rerank_movement is not None:
        if explanation.rerank_movement > 0:
            arrow = f"+{explanation.rerank_movement} (moved up)"
        elif explanation.rerank_movement < 0:
            arrow = f"{explanation.rerank_movement} (moved down)"
        else:
            arrow = "0 (held position)"
        table.add_row("Rerank:", arrow)

    if explanation.graph_fallback:
        table.add_row("Fallback:", "graph returned no hits -> vector")

    console.print(table)


@click.command("query")
@click.argument("query_text")
@click.option(
    "--url",
    envvar="AGENT_BRAIN_URL",
    default=None,
    help="Agent Brain server URL (default: from config or http://127.0.0.1:8000)",
)
@click.option(
    "-k",
    "--top-k",
    default=5,
    type=int,
    help="Number of results to return (default: 5)",
)
@click.option(
    "-t",
    "--threshold",
    default=0.3,
    type=float,
    help="Minimum similarity threshold 0-1 (default: 0.3)",
)
@click.option(
    "-m",
    "--mode",
    default="hybrid",
    type=click.Choice(
        ["vector", "bm25", "hybrid", "graph", "multi"], case_sensitive=False
    ),
    help=(
        "Retrieval mode: 'vector' (semantic similarity), 'bm25' (keyword matching), "
        "'hybrid' (vector+bm25), 'graph' (knowledge graph relationships, requires "
        "ENABLE_GRAPH_INDEX=true), 'multi' (fusion of vector+bm25+graph). "
        "Default: hybrid."
    ),
)
@click.option(
    "-a",
    "--alpha",
    default=0.5,
    type=float,
    help="Weight for hybrid search (1.0 = pure vector, 0.0 = pure bm25, default: 0.5)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--full", is_flag=True, help="Show full text content")
@click.option("--scores", is_flag=True, help="Show individual vector/BM25 scores")
@click.option(
    "--explain",
    is_flag=True,
    help=(
        "Show structured 'why this rank' explanations under each result: "
        "matched terms, fusion breakdown, graph path, and rerank movement "
        "(issue #159)."
    ),
)
@click.option(
    "--source-types",
    help="Comma-separated source types to filter by (doc,code,test)",
)
@click.option(
    "--languages",
    help="Comma-separated programming languages to filter by",
)
@click.option(
    "--file-paths",
    help="Comma-separated file path patterns to filter by (wildcards supported)",
)
@click.pass_context
def query_command(
    ctx: click.Context,
    query_text: str,
    url: str | None,
    top_k: int,
    threshold: float,
    mode: str,
    alpha: float,
    json_output: bool,
    full: bool,
    scores: bool,
    explain: bool,
    source_types: str | None,
    languages: str | None,
    file_paths: str | None,
) -> None:
    """Search indexed documents with natural language or keyword query."""
    if url:
        ctx.ensure_object(dict)
        ctx.obj["base_url_override"] = url
        ctx.obj["transport_hint"] = "http"

    # Parse comma-separated lists
    source_types_list = (
        [st.strip() for st in source_types.split(",")] if source_types else None
    )
    languages_list = (
        [lang.strip() for lang in languages.split(",")] if languages else None
    )
    file_paths_list = (
        [fp.strip() for fp in file_paths.split(",")] if file_paths else None
    )

    try:
        with open_client(ctx) as client:
            response = client.query(
                query_text=query_text,
                top_k=top_k,
                similarity_threshold=threshold,
                mode=mode.lower(),
                alpha=alpha,
                source_types=source_types_list,
                languages=languages_list,
                file_paths=file_paths_list,
                explain=explain,
            )

            if json_output:
                import json

                output = {
                    "query": query_text,
                    "total_results": response.total_results,
                    "query_time_ms": response.query_time_ms,
                    "results": [
                        {
                            "text": r.text,
                            "source": r.source,
                            "score": r.score,
                            "chunk_id": r.chunk_id,
                        }
                        for r in response.results
                    ],
                }
                click.echo(json.dumps(output, indent=2))
                return

            # Display header
            console.print(
                f"\n[bold]Query:[/] {query_text}\n"
                f"[dim]Found {response.total_results} results "
                f"in {response.query_time_ms:.1f}ms[/]\n"
            )

            if not response.results:
                console.print("[yellow]No matching documents found.[/]")
                console.print(
                    "\n[dim]Tips:\n"
                    "  - Try different keywords\n"
                    "  - Lower the threshold with --threshold 0.1\n"
                    "  - Check if documents are indexed with 'status' command[/]"
                )
                return

            # Display results
            for i, result in enumerate(response.results, 1):
                # Score color based on value
                if result.score >= 0.9:
                    score_color = "green"
                elif result.score >= 0.8:
                    score_color = "yellow"
                else:
                    score_color = "orange3"

                # Truncate text if not showing full
                text = result.text
                if not full and len(text) > 300:
                    text = text[:300] + "..."

                # Create result panel
                header = Text()
                header.append(f"[{i}] ", style="bold cyan")
                header.append(result.source, style="bold")
                header.append("  Score: ", style="dim")
                header.append(f"{result.score:.2%}", style=f"bold {score_color}")

                if scores:
                    header.append("  [V: ", style="dim")
                    v_score = result.metadata.get("vector_score") or getattr(
                        result, "vector_score", None
                    )
                    header.append(
                        f"{v_score:.2f}" if v_score is not None else "N/A", style="dim"
                    )
                    header.append(" B: ", style="dim")
                    b_score = result.metadata.get("bm25_score") or getattr(
                        result, "bm25_score", None
                    )
                    header.append(
                        f"{b_score:.2f}" if b_score is not None else "N/A", style="dim"
                    )
                    header.append("]", style="dim")

                console.print(
                    Panel(
                        text,
                        title=header,
                        border_style="dim",
                        padding=(0, 1),
                    )
                )

                # Issue #159: optional structured explanation block.
                if explain and result.explanation is not None:
                    _render_explanation(result.explanation)

    except ConnectionError as e:
        if json_output:
            import json

            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Connection Error:[/] {e}")
            console.print(f"[dim]{doctor_hint_message()}[/]")
        raise SystemExit(1) from e

    except ServerError as e:
        if json_output:
            import json

            click.echo(json.dumps({"error": str(e), "detail": e.detail}))
        else:
            console.print(f"[red]Server Error ({e.status_code}):[/] {e.detail}")
            if e.status_code == 503:
                console.print(
                    "\n[dim]The server is not ready. "
                    "Use 'status' to check, or 'index' to index documents.[/]"
                )
        raise SystemExit(1) from e
