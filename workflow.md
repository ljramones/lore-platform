export CHROMA=http://localhost:8000

# 1) List tenants (discover defaults)
curl -fsS $CHROMA/api/v2/tenants | jq .

# 2) Create a tenant (only if you don’t see one yet)
curl -fsS -X POST $CHROMA/api/v2/tenants \
  -H 'Content-Type: application/json' \
  -d '{"name":"local"}' | jq .

# 3) List DBs for that tenant
curl -fsS $CHROMA/api/v2/tenants/local/databases | jq .

# 4) Create a DB (only if needed)
curl -fsS -X POST $CHROMA/api/v2/tenants/local/databases \
  -H 'Content-Type: application/json' \
  -d '{"name":"lore"}' | jq .

# 5) Create a collection
curl -fsS -X POST $CHROMA/api/v2/tenants/local/databases/lore/collections \
  -H 'Content-Type: application/json' \
  -d '{"name":"smoke","metadata":{}}' | jq .

# 6) Grab the collection id
COL=$(
  curl -fsS $CHROMA/api/v2/tenants/local/databases/lore/collections \
  | jq -r '.collections[] | select(.name=="smoke") | .id'
)
echo "Collection ID: $COL"

# 7) Count items (should be 0)
curl -fsS $CHROMA/api/v2/tenants/local/databases/lore/collections/$COL/count | jq .

# 8) Upsert two vectors (no server embedder? send embeddings explicitly)
curl -fsS -X POST $CHROMA/api/v2/tenants/local/databases/lore/collections/$COL/upsert \
  -H 'Content-Type: application/json' \
  -d '{
        "ids": ["1","2"],
        "embeddings": [[0.1,0.2,0.3],[0.0,0.1,0.0]],
        "metadatas": [{"source":"smoke"},{"source":"smoke"}],
        "documents": ["hello world","storm goddess pact"]
      }' | jq .

# 9) Query nearest neighbor
curl -fsS -X POST $CHROMA/api/v2/tenants/local/databases/lore/collections/$COL/query \
  -H 'Content-Type: application/json' \
  -d '{"query_embeddings":[[0.1,0.21,0.31]], "n_results":1, "include":["documents","metadatas","distances"]}' | jq .

