# Update Graph

> Update an existing graph with new documents.

This endpoint processes additional documents based on the original graph filters
and/or new filters/document IDs, extracts entities and relationships, and
updates the graph with new information.

## OpenAPI

````yaml https://app.stainless.com/api/spec/documented/morphik/openapi.documented.yml post /graph/{name}/update
paths:
  path: /graph/{name}/update
  method: post
  request:
    security: []
    parameters:
      path:
        name:
          schema:
            - type: string
              required: true
              title: Name
      query: {}
      header:
        authorization:
          schema:
            - type: string
              required: false
              title: Authorization
      cookie: {}
    body:
      application/json:
        schemaArray:
          - type: object
            properties:
              additional_filters:
                allOf:
                  - anyOf:
                      - type: object
                      - type: 'null'
                    title: Additional Filters
                    description: >-
                      Optional additional metadata filters to determine which
                      new documents to include
              additional_documents:
                allOf:
                  - anyOf:
                      - items:
                          type: string
                        type: array
                      - type: 'null'
                    title: Additional Documents
                    description: Optional list of additional document IDs to include
              prompt_overrides:
                allOf:
                  - anyOf:
                      - $ref: '#/components/schemas/GraphPromptOverrides'
                      - type: 'null'
                    description: >-
                      Optional customizations for entity extraction and
                      resolution prompts
              folder_name:
                allOf:
                  - anyOf:
                      - type: string
                      - items:
                          type: string
                        type: array
                      - type: 'null'
                    title: Folder Name
                    description: >-
                      Optional folder scope for the operation. Accepts a single
                      folder name or a list of folder names.
              end_user_id:
                allOf:
                  - anyOf:
                      - type: string
                      - type: 'null'
                    title: End User Id
                    description: Optional end-user scope for the operation
            required: true
            title: UpdateGraphRequest
            description: Request model for updating a graph
            refIdentifier: '#/components/schemas/UpdateGraphRequest'
        examples:
          example:
            value:
              additional_filters: {}
              additional_documents:
                - <string>
              prompt_overrides:
                entity_extraction:
                  prompt_template: <string>
                  examples:
                    - label: <string>
                      type: <string>
                      properties: {}
                entity_resolution:
                  prompt_template: <string>
                  examples:
                    - canonical: <string>
                      variants:
                        - <string>
              folder_name: <string>
              end_user_id: <string>
    codeSamples:
      - lang: JavaScript
        source: |-
          import Morphik from 'morphik';

          const client = new Morphik({
            apiKey: 'My API Key',
          });

          const graph = await client.graph.update('name');

          console.log(graph.id);
      - lang: cURL
        source: |-
          curl https://api.morphik.ai/graph/$NAME/update \
              -H 'Content-Type: application/json' \
              -H "Authorization: Bearer $MORPHIK_API_KEY" \
              -d '{}'
  response:
    '200':
      application/json:
        schemaArray:
          - type: object
            properties:
              id:
                allOf:
                  - type: string
                    title: Id
              name:
                allOf:
                  - type: string
                    title: Name
              entities:
                allOf:
                  - items:
                      $ref: '#/components/schemas/Entity'
                    type: array
                    title: Entities
              relationships:
                allOf:
                  - items:
                      $ref: '#/components/schemas/Relationship'
                    type: array
                    title: Relationships
              metadata:
                allOf:
                  - type: object
                    title: Metadata
              system_metadata:
                allOf:
                  - type: object
                    title: System Metadata
              document_ids:
                allOf:
                  - items:
                      type: string
                    type: array
                    title: Document Ids
              filters:
                allOf:
                  - anyOf:
                      - type: object
                      - type: 'null'
                    title: Filters
              created_at:
                allOf:
                  - type: string
                    format: date-time
                    title: Created At
              updated_at:
                allOf:
                  - type: string
                    format: date-time
                    title: Updated At
              folder_name:
                allOf:
                  - anyOf:
                      - type: string
                      - type: 'null'
                    title: Folder Name
              end_user_id:
                allOf:
                  - anyOf:
                      - type: string
                      - type: 'null'
                    title: End User Id
              app_id:
                allOf:
                  - anyOf:
                      - type: string
                      - type: 'null'
                    title: App Id
            title: Graph
            description: Represents a knowledge graph
            refIdentifier: '#/components/schemas/Graph'
            requiredProperties:
              - name
        examples:
          example:
            value:
              id: <string>
              name: <string>
              entities:
                - id: <string>
                  label: <string>
                  type: <string>
                  properties: {}
                  document_ids:
                    - <string>
                  chunk_sources: {}
              relationships:
                - id: <string>
                  source_id: <string>
                  target_id: <string>
                  type: <string>
                  document_ids:
                    - <string>
                  chunk_sources: {}
              metadata: {}
              system_metadata: {}
              document_ids:
                - <string>
              filters: {}
              created_at: '2023-11-07T05:31:56Z'
              updated_at: '2023-11-07T05:31:56Z'
              folder_name: <string>
              end_user_id: <string>
              app_id: <string>
        description: Successful Response
    '422':
      application/json:
        schemaArray:
          - type: object
            properties:
              detail:
                allOf:
                  - items:
                      $ref: '#/components/schemas/ValidationError'
                    type: array
                    title: Detail
            title: HTTPValidationError
            refIdentifier: '#/components/schemas/HTTPValidationError'
        examples:
          example:
            value:
              detail:
                - loc:
                    - <string>
                  msg: <string>
                  type: <string>
        description: Validation Error
  deprecated: false
  type: path
components:
  schemas:
    Entity:
      properties:
        id:
          type: string
          title: Id
        label:
          type: string
          title: Label
        type:
          type: string
          title: Type
        properties:
          type: object
          title: Properties
        document_ids:
          items:
            type: string
          type: array
          title: Document Ids
        chunk_sources:
          additionalProperties:
            items:
              type: integer
            type: array
          type: object
          title: Chunk Sources
      type: object
      required:
        - label
        - type
      title: Entity
      description: Represents an entity in a knowledge graph
    EntityExtractionExample:
      properties:
        label:
          type: string
          title: Label
          description: The entity label (e.g., 'John Doe', 'Apple Inc.')
        type:
          type: string
          title: Type
          description: The entity type (e.g., 'PERSON', 'ORGANIZATION', 'PRODUCT')
        properties:
          anyOf:
            - type: object
            - type: 'null'
          title: Properties
          description: 'Optional properties of the entity (e.g., {''role'': ''CEO'', ''age'': 42})'
      type: object
      required:
        - label
        - type
      title: EntityExtractionExample
      description: >-
        Example entity for guiding entity extraction.


        Used to provide domain-specific examples to the LLM of what entities to
        extract.

        These examples help steer the extraction process toward entities
        relevant to your domain.
    EntityExtractionPromptOverride:
      properties:
        prompt_template:
          anyOf:
            - type: string
            - type: 'null'
          title: Prompt Template
          description: >-
            Custom prompt template, MUST include both {content} and {examples}
            placeholders. The {content} placeholder will be replaced with the
            text to analyze, and {examples} will be replaced with formatted
            examples.
        examples:
          anyOf:
            - items:
                $ref: '#/components/schemas/EntityExtractionExample'
              type: array
            - type: 'null'
          title: Examples
          description: >-
            Examples of entities to extract, used to guide the LLM toward
            domain-specific entity types and patterns.
      type: object
      title: EntityExtractionPromptOverride
      description: >-
        Configuration for customizing entity extraction prompts.


        This allows you to override both the prompt template used for entity
        extraction

        and provide domain-specific examples of entities to be extracted.


        If only examples are provided (without a prompt_template), they will be

        incorporated into the default prompt. If only prompt_template is
        provided,

        it will be used with default examples (if any).


        Required placeholders:

        - {content}: Will be replaced with the text to analyze for entity
        extraction

        - {examples}: Will be replaced with formatted examples of entities to
        extract


        Example prompt template:

        ```

        Extract entities from the following text. Look for entities similar to
        these examples:


        {examples}


        Text to analyze:

        {content}


        Extracted entities (in JSON format):

        ```
    EntityResolutionExample:
      properties:
        canonical:
          type: string
          title: Canonical
          description: The canonical (standard/preferred) form of the entity
        variants:
          items:
            type: string
          type: array
          title: Variants
          description: List of variant forms that should resolve to the canonical form
      type: object
      required:
        - canonical
        - variants
      title: EntityResolutionExample
      description: >-
        Example for entity resolution, showing how variants should be grouped.


        Entity resolution is the process of identifying when different
        references

        (variants) in text refer to the same real-world entity. These examples

        help the LLM understand domain-specific patterns for resolving entities.
    EntityResolutionPromptOverride:
      properties:
        prompt_template:
          anyOf:
            - type: string
            - type: 'null'
          title: Prompt Template
          description: >-
            Custom prompt template that MUST include both {entities_str} and
            {examples_json} placeholders. The {entities_str} placeholder will be
            replaced with the extracted entities, and {examples_json} will be
            replaced with JSON-formatted examples of entity resolution groups.
        examples:
          anyOf:
            - items:
                $ref: '#/components/schemas/EntityResolutionExample'
              type: array
            - type: 'null'
          title: Examples
          description: >-
            Examples of entity resolution groups showing how variants of the
            same entity should be resolved to their canonical forms. This is
            particularly useful for domain-specific terminology, abbreviations,
            and naming conventions.
      type: object
      title: EntityResolutionPromptOverride
      description: >-
        Configuration for customizing entity resolution prompts.


        Entity resolution identifies and groups variant forms of the same
        entity.

        This override allows you to customize how this process works by
        providing

        a custom prompt template and/or domain-specific examples.


        If only examples are provided (without a prompt_template), they will be

        incorporated into the default prompt. If only prompt_template is
        provided,

        it will be used with default examples (if any).


        Required placeholders:

        - {entities_str}: Will be replaced with the extracted entities

        - {examples_json}: Will be replaced with JSON-formatted examples of
        entity resolution groups


        Example prompt template:

        ```

        I have extracted the following entities:


        {entities_str}


        Below are examples of how different entity references can be grouped
        together:


        {examples_json}


        Group the above entities by resolving which mentions refer to the same
        entity.

        Return the results in JSON format.

        ```
    GraphPromptOverrides:
      properties:
        entity_extraction:
          anyOf:
            - $ref: '#/components/schemas/EntityExtractionPromptOverride'
            - type: 'null'
          description: >-
            Overrides for entity extraction prompts - controls how entities are
            identified in text during graph operations
        entity_resolution:
          anyOf:
            - $ref: '#/components/schemas/EntityResolutionPromptOverride'
            - type: 'null'
          description: >-
            Overrides for entity resolution prompts - controls how variant forms
            are grouped during graph operations
      additionalProperties: false
      type: object
      title: GraphPromptOverrides
      description: |-
        Container for graph-related prompt overrides.

        Use this class when customizing prompts for graph operations like
        create_graph() and update_graph(), which only support entity extraction
        and entity resolution customizations.

        This class enforces that only graph-relevant override types are used.
    Relationship:
      properties:
        id:
          type: string
          title: Id
        source_id:
          type: string
          title: Source Id
        target_id:
          type: string
          title: Target Id
        type:
          type: string
          title: Type
        document_ids:
          items:
            type: string
          type: array
          title: Document Ids
        chunk_sources:
          additionalProperties:
            items:
              type: integer
            type: array
          type: object
          title: Chunk Sources
      type: object
      required:
        - source_id
        - target_id
        - type
      title: Relationship
      description: Represents a relationship between entities in a knowledge graph
    ValidationError:
      properties:
        loc:
          items:
            anyOf:
              - type: string
              - type: integer
          type: array
          title: Location
        msg:
          type: string
          title: Message
        type:
          type: string
          title: Error Type
      type: object
      required:
        - loc
        - msg
        - type
      title: ValidationError

````

---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://morphik.ai/docs/llms.txt