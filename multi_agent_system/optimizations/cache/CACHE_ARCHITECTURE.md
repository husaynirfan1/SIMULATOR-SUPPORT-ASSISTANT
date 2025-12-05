# Response Cache Architecture

## System Flow with Caching

```mermaid
graph TD
    START([User Query]) --> CACHE{Check Cache}

    CACHE -->|Exact Match Found| HIT1[Cache HIT - Exact]
    CACHE -->|No Exact Match| FUZZY{Fuzzy Match?}

    FUZZY -->|Similar Query Found| HIT2[Cache HIT - Fuzzy]
    FUZZY -->|No Match| MISS[Cache MISS]

    HIT1 --> RETURN1[Return Cached Response - 0.05s]
    HIT2 --> RETURN2[Return Cached Response - 0.05s]

    MISS --> PLAN[Planning Node]
    PLAN --> SPECIALISTS[Consult Specialists]
    SPECIALISTS --> TOOLS[Execute Tools]
    TOOLS --> SYNTH[Synthesize Response]
    SYNTH --> STORE[Store in Cache]
    STORE --> RETURN3[Return Fresh Response - 5s]

    RETURN1 --> END([Response to User])
    RETURN2 --> END
    RETURN3 --> END

    style HIT1 fill:#4ade80,stroke:#16a34a,stroke-width:2px
    style HIT2 fill:#86efac,stroke:#16a34a,stroke-width:2px
    style MISS fill:#fca5a5,stroke:#dc2626,stroke-width:2px
    style RETURN1 fill:#4ade80,stroke:#16a34a,stroke-width:3px
    style RETURN2 fill:#86efac,stroke:#16a34a,stroke-width:3px
    style RETURN3 fill:#fbbf24,stroke:#f59e0b,stroke-width:2px
```

## Cache Matching Process

```mermaid
graph LR
    Q[Query] --> N[Normalize]
    N --> K[Generate Key]
    K --> E{Exact Match?}

    E -->|Yes| C1[✅ Cache Hit]
    E -->|No| F[Calculate Similarity]

    F --> S{Similarity >= 85%?}
    S -->|Yes| C2[✅ Fuzzy Hit]
    S -->|No| M[❌ Cache Miss]

    C1 --> R1[Return Response - Instant]
    C2 --> R2[Return Response - Instant]
    M --> R3[Execute Query - 5+ seconds]

    style C1 fill:#22c55e
    style C2 fill:#84cc16
    style M fill:#ef4444
```

## Query Normalization

```mermaid
graph LR
    Q["Original Query:<br/>  'What is a DR?'  "] --> LC[To Lowercase]
    LC --> TR[Trim Whitespace]
    TR --> RM[Remove Extra Spaces]
    RM --> RP[Remove Trailing Punctuation]
    RP --> NK["Normalized Key:<br/>'what is a dr'"]

    style Q fill:#dbeafe
    style NK fill:#86efac
```

## Cache Storage Structure

```mermaid
graph TD
    CACHE[Cache Storage - OrderedDict]

    CACHE --> E1["Entry 1<br/>key: hash('what is a dr')<br/>query: 'What is a DR?'<br/>response: {...}<br/>timestamp: 1234567890"]

    CACHE --> E2["Entry 2<br/>key: hash('interface issues')<br/>query: 'Interface issues?'<br/>response: {...}<br/>timestamp: 1234567900"]

    CACHE --> E3["Entry N<br/>key: hash('...')<br/>query: '...'<br/>response: {...}<br/>timestamp: ..."]

    E1 --> CHECK1{Expired?}
    E2 --> CHECK2{Expired?}
    E3 --> CHECK3{Expired?}

    CHECK1 -->|Yes| DEL1[Auto-Delete]
    CHECK2 -->|No| KEEP2[Keep]
    CHECK3 -->|No| KEEP3[Keep]

    style CACHE fill:#4ade80,stroke:#16a34a
    style DEL1 fill:#ef4444
    style KEEP2 fill:#86efac
    style KEEP3 fill:#86efac
```

## Fuzzy Matching Algorithm

```mermaid
graph TD
    Q1["Query 1:<br/>'What is a deficiency report?'"] --> T1[Tokenize]
    Q2["Query 2:<br/>'What's a deficiency report'"] --> T2[Tokenize]

    T1 --> S1["Tokens:<br/>{what, is, a, deficiency, report}"]
    T2 --> S2["Tokens:<br/>{what's, a, deficiency, report}"]

    S1 --> INT[Calculate Intersection]
    S2 --> INT

    INT --> I["Intersection:<br/>{a, deficiency, report}<br/>Count: 3"]

    S1 --> UN[Calculate Union]
    S2 --> UN

    UN --> U["Union:<br/>{what, is, a, what's, deficiency, report}<br/>Count: 6"]

    I --> SIM[Similarity = 3/6 = 0.50]
    U --> SIM

    SIM --> THR{>= 0.85?}
    THR -->|No| MISS[Cache Miss]
    THR -->|Yes| HIT[Cache Hit]

    style HIT fill:#22c55e
    style MISS fill:#ef4444
```

## Performance Comparison

### Without Cache
```mermaid
sequenceDiagram
    participant U as User
    participant S as System
    participant P as Planning
    participant A as Agents (5x)
    participant M as Morphik RAG
    participant L as LLM

    U->>S: Query: "What is a DR?"
    S->>P: Route query
    P->>L: LLM call (planning)
    L-->>P: Agent selection
    P->>A: Consult 5 agents
    loop Each Agent (5x)
        A->>M: RAG query (k=10, hop=2)
        M->>L: Generate response
        L-->>M: Response
        M-->>A: Answer
    end
    A-->>S: Combined results
    S->>L: Synthesize
    L-->>S: Final answer
    S-->>U: Response (5+ seconds)
```

### With Cache (Hit)
```mermaid
sequenceDiagram
    participant U as User
    participant S as System
    participant C as Cache

    U->>S: Query: "What is a DR?"
    S->>C: Check cache
    C-->>S: ✅ HIT - Return cached response
    S-->>U: Response (0.05 seconds)

    Note over S,C: 100x faster!
```

## Cache Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Empty: System Start
    Empty --> Filling: Queries arrive
    Filling --> Active: Cache populated
    Active --> Active: Cache hits/misses
    Active --> Full: Max size reached
    Full --> Full: LRU eviction
    Active --> Expired: TTL exceeded
    Expired --> Active: Cleanup
    Active --> Empty: Manual clear
    Empty --> [*]: System shutdown
```

## Thread Safety

```mermaid
graph TD
    T1[Thread 1 - GET] --> LOCK{Acquire Lock}
    T2[Thread 2 - SET] --> LOCK
    T3[Thread 3 - GET] --> LOCK

    LOCK -->|Thread 1 First| OP1[Read Cache]
    OP1 --> REL1[Release Lock]

    REL1 --> LOCK2{Acquire Lock}
    LOCK2 -->|Thread 2 Next| OP2[Write Cache]
    OP2 --> REL2[Release Lock]

    REL2 --> LOCK3{Acquire Lock}
    LOCK3 -->|Thread 3 Next| OP3[Read Cache]
    OP3 --> REL3[Release Lock]

    style LOCK fill:#fbbf24
    style LOCK2 fill:#fbbf24
    style LOCK3 fill:#fbbf24
```

## Cache Hit Rate Over Time

```mermaid
graph LR
    T0[Start<br/>Hit Rate: 0%] --> T1[100 queries<br/>Hit Rate: 15%]
    T1 --> T2[500 queries<br/>Hit Rate: 35%]
    T2 --> T3[1000 queries<br/>Hit Rate: 55%]
    T3 --> T4[2000+ queries<br/>Hit Rate: 70%+]

    style T0 fill:#ef4444
    style T1 fill:#f59e0b
    style T2 fill:#fbbf24
    style T3 fill:#84cc16
    style T4 fill:#22c55e
```

## Integration Points

```mermaid
graph TD
    GRAPH[graph.py] --> CACHE[response_cache.py]
    SERVER[server.py] --> GRAPH

    GRAPH -->|query method| CHECK[Check cache]
    CHECK -->|miss| EXEC[Execute workflow]
    EXEC -->|success| STORE[Store response]

    CHECK -->|hit| RETURN[Return cached]

    SERVER -->|GET /cache/stats| STATS[Cache statistics]
    SERVER -->|DELETE /cache/clear| CLEAR[Clear cache]
    SERVER -->|GET /cache/queries| LIST[List entries]

    CACHE --> STATS
    CACHE --> CLEAR
    CACHE --> LIST

    style CACHE fill:#4ade80,stroke:#16a34a,stroke-width:2px
    style GRAPH fill:#60a5fa,stroke:#2563eb,stroke-width:2px
    style SERVER fill:#c084fc,stroke:#9333ea,stroke-width:2px
```

## Memory Usage

```mermaid
graph TD
    CACHE[Cache Memory] --> ENTRY[Per Entry]

    ENTRY --> QUERY["Query string<br/>~100 bytes"]
    ENTRY --> RESPONSE["Response dict<br/>~5-10 KB"]
    ENTRY --> META["Metadata<br/>~50 bytes"]

    ENTRY --> TOTAL["Total: ~5-10 KB per entry"]

    TOTAL --> SIZE["Cache Size = 100 entries<br/>Memory: 500 KB - 1 MB"]

    style SIZE fill:#86efac
```

---

## Summary

The response cache provides:
- ✅ **100x speed improvement** for cached queries
- ✅ **Fuzzy matching** for similar queries
- ✅ **Automatic expiration** (TTL-based)
- ✅ **LRU eviction** when full
- ✅ **Thread-safe** operations
- ✅ **Low memory footprint** (~1MB for 100 entries)

Perfect for FAQ scenarios where users ask the same questions repeatedly!
