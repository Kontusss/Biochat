"""
Biochat utility functions — re-exported from sub-modules.

This package replaces the monolithic ``biochat/utils.py`` (2366 lines)
with 12 focused sub-modules.  All original function names are preserved
as backward-compatible aliases.
"""

# ── Code execution ───────────────────────────────────────────────
from biochat.utils.code_execution import (
    execute_bash_script,
    execute_cli_command,
    execute_r_script,
    execute_with_thread_timeout,
    run_bash_script,
    run_cli_command,
    run_r_code,
    run_with_timeout,
)

# ── API schema ───────────────────────────────────────────────────
from biochat.utils.api_schema import (
    ApiSchema,
    EnhancedBaseModel,
    convert_schema_to_langchain_tool,
    extract_tool_decorated_functions,
    extract_top_level_functions,
    generate_api_schema_from_code,
    wrap_with_safe_execution,
    api_schema,
    api_schema_to_langchain_tool,
    CustomBaseModel,
    function_to_api_schema,
    get_all_functions_from_file,
    get_tool_decorated_functions,
    safe_execute_decorator,
)

# ── Gene ID ──────────────────────────────────────────────────────
from biochat.utils.gene_id import (
    GeneIDType,
    get_gene_id,
    resolve_ensembl_id,
    resolve_ensembl_versioned_id,
    resolve_entrez_id,
    ID,
    _get_gene_id_ensembl,
    _get_gene_id_ensembl_with_version,
    _get_gene_id_entrez,
)

# ── S3 / download ────────────────────────────────────────────────
from biochat.utils.s3_download import (
    fetch_and_extract_archive,
    sync_data_lake_files,
    check_and_download_s3_files,
    download_and_unzip,
)

# ── Message format ───────────────────────────────────────────────
from biochat.utils.message_format import (
    convert_langchain_message_to_gradio,
    format_langchain_message_for_display,
    langchain_to_gradio_message,
    pretty_print,
)

# ── PDF ──────────────────────────────────────────────────────────
from biochat.utils.pdf_css import get_pdf_css_content
from biochat.utils.pdf_export import convert_markdown_to_pdf, execute_with_timeout

# ── Text format ──────────────────────────────────────────────────
from biochat.utils.text_format import (
    find_matching_execution,
    format_checkbox_lists,
    has_execution_results,
    render_execute_tags_as_html,
    render_observation_block,
    clean_code_content,
    create_tool_call_block,
    detect_code_language_and_tool,
    format_default_tool_name,
    format_detected_tools,
    format_execute_tags_in_content,
    format_lists_in_text,
    format_observation_as_terminal,
    format_solution_tags_in_content,
    identify_list_blocks,
    process_observation_with_images,
    format_single_list,
)

# ── Tool parser ──────────────────────────────────────────────────
from biochat.utils.tool_parser import (
    detect_tool_imports,
    detect_tool_imports_with_modules,
    register_custom_functions_in_namespace,
    find_best_module_match,
    inject_custom_functions_to_repl,
    parse_tool_calls_from_code,
    parse_tool_calls_with_modules,
)

# ── I/O ──────────────────────────────────────────────────────────
from biochat.utils.io_utils import (
    ensure_directory_exists,
    format_api_dict_as_text,
    load_all_tool_descriptions,
    load_pickle,
    load_pkl,
    save_pickle,
    save_pkl,
    check_or_create_path,
    read_module2api,
    textify_api_dict,
)

# ── Logging ──────────────────────────────────────────────────────
from biochat.utils.logging_utils import (
    NodeLogger,
    PromptLogger,
    ansi_print,
    color_print,
)

# ── Text cleanup ─────────────────────────────────────────────────
from biochat.utils.text_cleanup import (
    build_parsing_error_html,
    is_message_empty,
    strip_ansi_escape_codes,
    strip_emojis,
    clean_message_content,
    create_parsing_error_html,
    remove_emojis_from_text,
    should_skip_message,
)

# ── GraphQL & misc ───────────────────────────────────────────────
from biochat.utils.graphql_utils import (
    build_retrieval_corpus,
    execute_graphql_query,
    generate_python_code_with_llm,
    parse_hpo_obo,
    process_bio_retrieval_ducoment,
    write_python_code,
)
