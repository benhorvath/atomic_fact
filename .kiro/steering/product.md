# Product Overview

atomic-fact is a CLI tool that extracts "atomic facts" from text documents using the OpenAI API.

## What is an Atomic Fact?

An atomic fact (also called an "atomic claim", "data point", "evidence fragment", or "information unit") is a single, specific statement of fact extracted from an investigative or "detective" viewpoint. General knowledge is excluded.

An atomic fact must be:
- Explicitly stated or strongly implied in the text
- Specific (who, what, when, where)
- Non-trivial (not general knowledge)
- Atomic (one fact only)

Atomic facts typically contain proper nouns, dates, people, places, or other named entities.

Examples:
- Included: "Congressman Wayne met with the president on October 4, 1968"
- Excluded: "Water is made up of hydrogen and oxygen atoms"

## Input

Plain text files (.txt). Future versions may add modules for ingesting other document types (PDFs, etc.).

## Output

JSON array of atomic fact objects. Each fact includes:
- `fact`: The atomic fact as a clear standalone statement
- `quote`: The corresponding verbatim quote from the source text
- `entities`: Detected proper nouns / named entities (people, places, organizations, etc.)
- `dates`: Detected dates, standardized to ISO 8601 format where possible
- `confidence`: A confidence level for the extraction (e.g., high / medium / low)

## LLM Usage

- Uses the OpenAI API for extraction
- Default model: latest available (currently gpt-4o), configurable via CLI flag or environment variable

## Future Considerations

- Additional input formats (PDF, HTML, etc.)
- General knowledge filtering as a post-processing step
