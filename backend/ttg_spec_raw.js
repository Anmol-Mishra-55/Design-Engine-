
window.onload = function() {
  // Build a system
  var url = window.location.search.match(/url=([^&]+)/);
  if (url && url.length > 1) {
    url = decodeURIComponent(url[1]);
  } else {
    url = window.location.origin;
  }
  var options = {
  "swaggerDoc": {
    "openapi": "3.0.0",
    "info": {
      "title": "Real-Time Micro-Bridge API",
      "version": "1.0.0",
      "description": "## Real-Time Micro-Bridge + Multi-Agent Orchestrator\n\n**HTTP Base URL:** `http://localhost:3000`\n**WebSocket URL:** `ws://localhost:3000`\n\n---\n\n### Socket.IO Namespaces\n| Namespace | Purpose |\n|---|---|\n| `/` (default) | Dashboard clients — presence, actions, agents, jobs |\n| `/engine` | Game engine — job dispatch, telemetry, game events |\n| `/simulate/stream` | Real-time simulation tick streaming |\n\n---\n\n### TTG Runtime Flow\n```\nPOST /api/intent/compile       → get gameplay contract\nPOST /core/execute             → dispatch to engine queue\n  └─ Socket /engine job:dispatch → engine receives job\n  └─ Socket game:started        → SimEngine runs\n  └─ Socket sim_result          → broadcast to dashboard\n  └─ Socket runtime_event       → state update + consequence jobs\nGET  /core/execution/:id       → poll status\nGET  /core/game-state/:id      → live game state\n```"
    },
    "servers": [
      {
        "url": "http://localhost:3000",
        "description": "Local dev server"
      }
    ],
    "tags": [
      {
        "name": "Auth",
        "description": "JWT token endpoints"
      },
      {
        "name": "TTG — Compile & Assets",
        "description": "Text-to-Game: compile text → gameplay contract + engine capabilities"
      },
      {
        "name": "Core Execution",
        "description": "Submit and track execution schemas through the engine pipeline"
      },
      {
        "name": "Game State",
        "description": "Live game state, sessions, and deterministic replay"
      },
      {
        "name": "Execution Interface",
        "description": "Phase 4 hardened contract entry point (engineExecutionContract_v3)"
      },
      {
        "name": "Pipeline",
        "description": "Maritime governance pipeline — run, replay, artifacts, telemetry"
      },
      {
        "name": "Simulation",
        "description": "Deterministic SumScript simulation engine — run, replay, results"
      },
      {
        "name": "TTS",
        "description": "Text-to-speech audio generation"
      },
      {
        "name": "Socket.IO — Dashboard",
        "description": "⚡ Default namespace `/`. Connect with Bearer JWT. Handles presence, actions, agents, heartbeat, job status."
      },
      {
        "name": "Socket.IO — Engine",
        "description": "⚡ Namespace `/engine`. Engine authenticates with engine JWT. Handles job dispatch, telemetry, game lifecycle, runtime events."
      },
      {
        "name": "Socket.IO — Sim Stream",
        "description": "⚡ Namespace `/simulate/stream`. Real-time simulation tick streaming and replay."
      }
    ],
    "components": {
      "securitySchemes": {
        "BearerAuth": {
          "type": "http",
          "scheme": "bearer",
          "bearerFormat": "JWT"
        }
      },
      "schemas": {
        "Error": {
          "type": "object",
          "properties": {
            "success": {
              "type": "boolean",
              "example": false
            },
            "error": {
              "type": "string"
            }
          }
        },
        "GameplayContract": {
          "type": "object",
          "description": "Full gameplay contract — output of /api/intent/compile, input to /core/execute as executionSchema",
          "properties": {
            "game_mode": {
              "type": "string",
              "enum": [
                "runner",
                "sidescroller",
                "arena"
              ]
            },
            "movement": {
              "type": "object",
              "properties": {
                "speed": {
                  "type": "number",
                  "example": 5
                }
              }
            },
            "spawn_rules": {
              "type": "object",
              "properties": {
                "obstacles": {
                  "type": "integer",
                  "example": 3
                },
                "frequency": {
                  "type": "number",
                  "example": 2
                },
                "distance": {
                  "type": "number",
                  "example": 10
                }
              }
            },
            "player_params": {
              "type": "object",
              "properties": {
                "health": {
                  "type": "integer",
                  "example": 3
                },
                "jetpack": {
                  "type": "boolean",
                  "example": false
                },
                "jump_height": {
                  "type": "number",
                  "example": 5
                }
              }
            },
            "physics": {
              "type": "object",
              "properties": {
                "gravity": {
                  "type": "number",
                  "example": -9.8
                },
                "friction": {
                  "type": "number",
                  "example": 0.1
                },
                "bounce": {
                  "type": "number",
                  "example": 0
                },
                "air_resistance": {
                  "type": "number",
                  "example": 0.05
                },
                "collision_force": {
                  "type": "number",
                  "example": 1
                }
              }
            },
            "score_rules": {
              "type": "object",
              "example": {
                "distance": 1,
                "collectibles": 10
              }
            },
            "end_conditions": {
              "type": "array",
              "items": {
                "type": "string"
              },
              "example": [
                "collision"
              ]
            }
          }
        },
        "ExecutionSchema": {
          "type": "object",
          "required": [
            "execution_id",
            "trace_id",
            "executionSchema"
          ],
          "properties": {
            "execution_id": {
              "type": "string",
              "example": "exec_001"
            },
            "trace_id": {
              "type": "string",
              "example": "trace_001"
            },
            "user_id": {
              "type": "string",
              "example": "user_01"
            },
            "timestamp": {
              "type": "number",
              "example": 1700000000000
            },
            "intent": {
              "type": "string",
              "example": "fast runner with obstacles"
            },
            "executionSchema": {
              "$ref": "#/components/schemas/GameplayContract"
            }
          }
        },
        "JobStatus": {
          "type": "object",
          "properties": {
            "jobId": {
              "type": "string"
            },
            "jobType": {
              "type": "string",
              "enum": [
                "BUILD_SCENE",
                "SPAWN_ENTITY",
                "SPAWN_PLAYER",
                "SPAWN_OBSTACLE_SYSTEM",
                "SPAWN_ENEMIES",
                "SPAWN_PLATFORMS",
                "SPAWN_PICKUPS",
                "START_LOOP",
                "START_GAME",
                "STOP_GAME"
              ]
            },
            "status": {
              "type": "string",
              "enum": [
                "queued",
                "dispatched",
                "running",
                "completed",
                "failed"
              ]
            },
            "priority": {
              "type": "string",
              "example": "medium"
            },
            "submittedAt": {
              "type": "number"
            },
            "executionId": {
              "type": "string"
            },
            "templateId": {
              "type": "string",
              "nullable": true
            },
            "error": {
              "type": "string",
              "nullable": true
            }
          }
        }
      }
    },
    "paths": {
      "/health": {
        "get": {
          "tags": [
            "Auth"
          ],
          "summary": "Server health check",
          "responses": {
            "200": {
              "description": "Server is up",
              "content": {
                "application/json": {
                  "schema": {
                    "type": "object",
                    "properties": {
                      "status": {
                        "type": "string",
                        "example": "ok"
                      },
                      "uptime": {
                        "type": "number",
                        "description": "seconds"
                      },
                      "timestamp": {
                        "type": "number"
                      }
                    }
                  }
                }
              }
            }
          }
        }
      },
      "/auth/token": {
        "post": {
          "tags": [
            "Auth"
          ],
          "summary": "Get a JWT for a user",
          "description": "Assigns role=admin if userId is in allowlist (admin, testadmin, root), otherwise role=user.",
          "requestBody": {
            "required": true,
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "required": [
                    "userId"
                  ],
                  "properties": {
                    "userId": {
                      "type": "string",
                      "example": "admin"
                    }
                  }
                }
              }
            }
          },
          "responses": {
            "200": {
              "description": "JWT token",
              "content": {
                "application/json": {
                  "schema": {
                    "type": "object",
                    "properties": {
                      "token": {
                        "type": "string"
                      }
                    }
                  }
                }
              }
            },
            "400": {
              "description": "userId required"
            }
          }
        }
      },
      "/auth/engine-token": {
        "get": {
          "tags": [
            "Auth"
          ],
          "summary": "Get long-lived engine JWT (365d) — use to connect to /engine Socket.IO namespace",
          "responses": {
            "200": {
              "description": "Engine JWT",
              "content": {
                "application/json": {
                  "schema": {
                    "type": "object",
                    "properties": {
                      "token": {
                        "type": "string"
                      },
                      "engineId": {
                        "type": "string",
                        "example": "atharva_engine_01"
                      },
                      "expiresIn": {
                        "type": "string",
                        "example": "365 days"
                      },
                      "usage": {
                        "type": "string"
                      }
                    }
                  }
                }
              }
            }
          }
        }
      },
      "/auth/static-user-token": {
        "get": {
          "tags": [
            "Auth"
          ],
          "summary": "Get permanent demo user token (365d) — for dashboard access",
          "responses": {
            "200": {
              "description": "Static user JWT",
              "content": {
                "application/json": {
                  "schema": {
                    "type": "object",
                    "properties": {
                      "token": {
                        "type": "string"
                      },
                      "userId": {
                        "type": "string",
                        "example": "user_static_demo"
                      },
                      "expiresIn": {
                        "type": "string",
                        "example": "365 days"
                      },
                      "usage": {
                        "type": "string"
                      }
                    }
                  }
                }
              }
            }
          }
        }
      },
      "/api/intent/compile": {
        "post": {
          "tags": [
            "TTG — Compile & Assets"
          ],
          "summary": "Compile natural language text → gameplay contract",
          "description": "Converts user text into a full gameplay contract.\nThe returned `schema` is the **gameplay contract** — pass it as `executionSchema` to `POST /core/execute`.\n\n**Validation:** min 3 / max 500 chars, letters/numbers/spaces/basic punctuation only, no HTML, no JSON.",
          "requestBody": {
            "required": true,
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "required": [
                    "text"
                  ],
                  "properties": {
                    "text": {
                      "type": "string",
                      "example": "fast runner game with obstacles and jetpack"
                    },
                    "userId": {
                      "type": "string",
                      "example": "user_01"
                    }
                  }
                },
                "examples": {
                  "runner": {
                    "summary": "Runner",
                    "value": {
                      "text": "fast runner game with obstacles",
                      "userId": "user_01"
                    }
                  },
                  "platformer": {
                    "summary": "Platformer",
                    "value": {
                      "text": "easy platformer with jump and coins",
                      "userId": "user_01"
                    }
                  },
                  "arena": {
                    "summary": "Arena",
                    "value": {
                      "text": "hard arena survival with enemies",
                      "userId": "user_01"
                    }
                  }
                }
              }
            }
          },
          "responses": {
            "200": {
              "description": "Compiled gameplay contract",
              "content": {
                "application/json": {
                  "schema": {
                    "type": "object",
                    "properties": {
                      "success": {
                        "type": "boolean",
                        "example": true
                      },
                      "intent": {
                        "type": "object",
                        "properties": {
                          "genre": {
                            "type": "string",
                            "enum": [
                              "runner",
                              "sidescroller"
                            ]
                          },
                          "pacing": {
                            "type": "string",
                            "enum": [
                              "slow",
                              "medium",
                              "fast"
                            ]
                          },
                          "difficulty": {
                            "type": "string",
                            "enum": [
                              "easy",
                              "medium",
                              "hard"
                            ]
                          },
                          "abilities": {
                            "type": "array",
                            "items": {
                              "type": "string"
                            },
                            "example": [
                              "jump",
                              "jetpack"
                            ]
                          },
                          "obstacles": {
                            "type": "boolean"
                          },
                          "pickups": {
                            "type": "boolean"
                          }
                        }
                      },
                      "schema": {
                        "$ref": "#/components/schemas/GameplayContract"
                      },
                      "message": {
                        "type": "string",
                        "example": "Compiled runner game"
                      }
                    }
                  }
                }
              }
            },
            "400": {
              "description": "Validation failed or contract violation"
            },
            "500": {
              "description": "Server error"
            }
          }
        }
      },
      "/api/intent/features": {
        "get": {
          "tags": [
            "TTG — Compile & Assets"
          ],
          "summary": "Get supported TTG features — genres, abilities, difficulty, pacing",
          "responses": {
            "200": {
              "description": "Supported features",
              "content": {
                "application/json": {
                  "schema": {
                    "type": "object",
                    "properties": {
                      "success": {
                        "type": "boolean"
                      },
                      "features": {
                        "type": "object",
                        "properties": {
                          "genres": {
                            "type": "array",
                            "items": {
                              "type": "string"
                            },
                            "example": [
                              "runner",
                              "sidescroller"
                            ]
                          },
                          "abilities": {
                            "type": "array",
                            "items": {
                              "type": "string"
                            },
                            "example": [
                              "jump",
                              "dash",
                              "jetpack"
                            ]
                          },
                          "difficulty": {
                            "type": "array",
                            "items": {
                              "type": "string"
                            },
                            "example": [
                              "easy",
                              "medium",
                              "hard"
                            ]
                          },
                          "pacing": {
                            "type": "array",
                            "items": {
                              "type": "string"
                            },
                            "example": [
                              "slow",
                              "medium",
                              "fast"
                            ]
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      },
      "/api/intent/engine-capabilities": {
        "get": {
          "tags": [
            "TTG — Compile & Assets"
          ],
          "summary": "Get engine gameplay asset registry — entities, components, job types",
          "description": "Returns every asset the engine supports. Use to validate contracts before dispatch.",
          "responses": {
            "200": {
              "description": "Engine capabilities",
              "content": {
                "application/json": {
                  "schema": {
                    "type": "object",
                    "properties": {
                      "entities": {
                        "type": "array",
                        "items": {
                          "type": "string"
                        },
                        "example": [
                          "player",
                          "enemy",
                          "obstacle",
                          "obstacle_spawner",
                          "pickup",
                          "ground",
                          "platform",
                          "spawner",
                          "checkpoint"
                        ]
                      },
                      "components": {
                        "type": "array",
                        "items": {
                          "type": "string"
                        },
                        "example": [
                          "runner_controller",
                          "platformer_controller",
                          "arena_controller",
                          "ai_controller",
                          "collider",
                          "mesh",
                          "rigidbody",
                          "health",
                          "trigger"
                        ]
                      },
                      "jobs": {
                        "type": "array",
                        "items": {
                          "type": "string"
                        },
                        "example": [
                          "BUILD_SCENE",
                          "SPAWN_ENTITY",
                          "SPAWN_PLAYER",
                          "SPAWN_OBSTACLE_SYSTEM",
                          "SPAWN_ENEMIES",
                          "SPAWN_PLATFORMS",
                          "SPAWN_PICKUPS",
                          "START_LOOP"
                        ]
                      }
                    }
                  }
                }
              }
            }
          }
        }
      },
      "/api/intent/gameplay-assets": {
        "get": {
          "tags": [
            "TTG — Compile & Assets"
          ],
          "summary": "Get all game templates with entities, components, jobs, and default parameters",
          "description": "Returns the full template definition for each game mode (runner, platformer, arena). Use this to understand what assets and jobs each mode requires before dispatching.",
          "responses": {
            "200": {
              "description": "All gameplay templates keyed by game mode",
              "content": {
                "application/json": {
                  "schema": {
                    "type": "object",
                    "properties": {
                      "success": {
                        "type": "boolean",
                        "example": true
                      },
                      "gameplay_assets": {
                        "type": "object",
                        "properties": {
                          "runner": {
                            "type": "object",
                            "properties": {
                              "template_id": {
                                "type": "string",
                                "example": "runner_v1"
                              },
                              "entities": {
                                "type": "array",
                                "items": {
                                  "type": "string"
                                },
                                "example": [
                                  "player",
                                  "ground",
                                  "obstacle_spawner"
                                ]
                              },
                              "components": {
                                "type": "object",
                                "example": {
                                  "player": [
                                    "runner_controller",
                                    "collider"
                                  ]
                                }
                              },
                              "jobs": {
                                "type": "array",
                                "items": {
                                  "type": "string"
                                },
                                "example": [
                                  "BUILD_SCENE",
                                  "SPAWN_PLAYER",
                                  "SPAWN_OBSTACLE_SYSTEM",
                                  "START_LOOP"
                                ]
                              },
                              "defaults": {
                                "type": "object",
                                "example": {
                                  "movement_speed": 5,
                                  "spawn_frequency": 3,
                                  "gravity": -9.8
                                }
                              }
                            }
                          },
                          "platformer": {
                            "type": "object",
                            "description": "Platformer template (same shape as runner)"
                          },
                          "arena": {
                            "type": "object",
                            "description": "Arena template (same shape as runner)"
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      },
      "/api/intent/runtime-consumption": {
        "get": {
          "tags": [
            "TTG — Compile & Assets"
          ],
          "summary": "Get estimated runtime resource consumption per game mode",
          "description": "Returns job count, entities spawned, estimated tick cost (ms), and memory estimate for each game mode. Optionally filter by `?game_mode=runner|platformer|arena`.",
          "parameters": [
            {
              "name": "game_mode",
              "in": "query",
              "required": false,
              "schema": {
                "type": "string",
                "enum": [
                  "runner",
                  "platformer",
                  "arena"
                ]
              },
              "description": "Filter to a single game mode"
            }
          ],
          "responses": {
            "200": {
              "description": "Runtime consumption data",
              "content": {
                "application/json": {
                  "schema": {
                    "type": "object",
                    "properties": {
                      "success": {
                        "type": "boolean",
                        "example": true
                      },
                      "consumption": {
                        "type": "object",
                        "description": "Keyed by game_mode when no filter, or single object when filtered",
                        "example": {
                          "runner": {
                            "game_mode": "runner",
                            "jobs_dispatched": [
                              "BUILD_SCENE",
                              "SPAWN_PLAYER",
                              "SPAWN_OBSTACLE_SYSTEM",
                              "START_LOOP"
                            ],
                            "job_count": 4,
                            "entities_spawned": [
                              "player",
                              "ground",
                              "obstacle_spawner"
                            ],
                            "estimated_tick_cost_ms": 12,
                            "memory_estimate_mb": 32,
                            "notes": "Lightweight — single lane, no AI agents"
                          }
                        }
                      }
                    }
                  }
                }
              }
            },
            "400": {
              "description": "Unknown game_mode value"
            }
          }
        }
      },
      "/core/execute": {
        "post": {
          "tags": [
            "Core Execution"
          ],
          "summary": "Submit gameplay contract for engine dispatch (security-enforced)",
          "description": "Main execution entry point. Validates signature + nonce, then dispatches through:\n1. Mitra governance check (ALLOW / BLOCK / FLAG)\n2. Enforcement gate (gateResult.passed must be true)\n3. Game state session initialized\n4. Template selected (runner / platformer / arena)\n5. Jobs created: BUILD_SCENE → SPAWN_PLAYER → SPAWN_OBSTACLE_SYSTEM → START_LOOP\n6. Each job dispatched to engine via Socket.IO `/engine` namespace",
          "requestBody": {
            "required": true,
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ExecutionSchema"
                }
              }
            }
          },
          "responses": {
            "200": {
              "description": "Accepted and queued",
              "content": {
                "application/json": {
                  "schema": {
                    "type": "object",
                    "properties": {
                      "success": {
                        "type": "boolean",
                        "example": true
                      },
                      "execution_id": {
                        "type": "string"
                      },
                      "trace_id": {
                        "type": "string"
                      },
                      "status": {
                        "type": "string",
                        "example": "received"
                      },
                      "message": {
                        "type": "string"
                      }
                    }
                  }
                }
              }
            },
            "401": {
              "description": "Security validation failed — bad signature, expired nonce, or timestamp skew"
            },
            "500": {
              "description": "Server error"
            }
          }
        }
      },
      "/core/execute-from-text": {
        "post": {
          "tags": [
            "Core Execution"
          ],
          "summary": "One-shot: natural language → compile → dispatch via Prompt Runner (Groq AI)",
          "requestBody": {
            "required": true,
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "required": [
                    "prompt"
                  ],
                  "properties": {
                    "prompt": {
                      "type": "string",
                      "example": "Create a fast runner game in a desert with obstacles"
                    },
                    "user_id": {
                      "type": "string",
                      "example": "user_01"
                    }
                  }
                }
              }
            }
          },
          "responses": {
            "200": {
              "description": "Prompt compiled and execution queued"
            },
            "400": {
              "description": "Missing or invalid prompt"
            },
            "500": {
              "description": "Prompt Runner error"
            }
          }
        }
      },
      "/core/prompt-runner-compile": {
        "post": {
          "tags": [
            "Core Execution"
          ],
          "summary": "Compile prompt via Groq AI — preview only, no dispatch",
          "requestBody": {
            "required": true,
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "required": [
                    "prompt"
                  ],
                  "properties": {
                    "prompt": {
                      "type": "string",
                      "example": "runner game in a volcano"
                    }
                  }
                }
              }
            }
          },
          "responses": {
            "200": {
              "description": "Compiled executionSchema (not dispatched)"
            },
            "400": {
              "description": "Missing prompt"
            },
            "500": {
              "description": "Server error"
            }
          }
        }
      },
      "/core/prompt-runner-health": {
        "get": {
          "tags": [
            "Core Execution"
          ],
          "summary": "Check Prompt Runner (Groq AI) service health",
          "responses": {
            "200": {
              "description": "Health status",
              "content": {
                "application/json": {
                  "schema": {
                    "type": "object",
                    "properties": {
                      "success": {
                        "type": "boolean"
                      },
                      "healthy": {
                        "type": "boolean"
                      },
                      "url": {
                        "type": "string",
                        "example": "http://127.0.0.1:8001"
                      }
                    }
                  }
                }
              }
            }
          }
        }
      },
      "/core/execute-from-prompt": {
        "post": {
          "tags": [
            "Core Execution"
          ],
          "summary": "LOCKED — returns 403. Use /core/execute-from-text instead.",
          "responses": {
            "403": {
              "description": "Direct prompt execution not allowed"
            }
          }
        }
      },
      "/core/execution/{id}": {
        "get": {
          "tags": [
            "Core Execution"
          ],
          "summary": "Get execution status and job progress by ID",
          "parameters": [
            {
              "name": "id",
              "in": "path",
              "required": true,
              "schema": {
                "type": "string"
              },
              "example": "exec_001"
            },
            {
              "name": "detailed",
              "in": "query",
              "schema": {
                "type": "string",
                "enum": [
                  "true",
                  "false"
                ]
              },
              "description": "true = include full jobDetails array"
            }
          ],
          "responses": {
            "200": {
              "description": "Execution state",
              "content": {
                "application/json": {
                  "schema": {
                    "type": "object",
                    "properties": {
                      "success": {
                        "type": "boolean"
                      },
                      "execution": {
                        "type": "object",
                        "properties": {
                          "execution_id": {
                            "type": "string"
                          },
                          "trace_id": {
                            "type": "string"
                          },
                          "status": {
                            "type": "string",
                            "enum": [
                              "received",
                              "running",
                              "completed",
                              "failed"
                            ]
                          },
                          "progress": {
                            "type": "number",
                            "description": "0–100 percent"
                          },
                          "jobs": {
                            "type": "object",
                            "properties": {
                              "total": {
                                "type": "integer"
                              },
                              "completed": {
                                "type": "integer"
                              },
                              "failed": {
                                "type": "integer"
                              },
                              "running": {
                                "type": "integer"
                              },
                              "queued": {
                                "type": "integer"
                              }
                            }
                          },
                          "receivedAt": {
                            "type": "number"
                          },
                          "startedAt": {
                            "type": "number"
                          },
                          "completedAt": {
                            "type": "number"
                          },
                          "duration": {
                            "type": "number",
                            "description": "milliseconds"
                          },
                          "error": {
                            "type": "string",
                            "nullable": true
                          }
                        }
                      }
                    }
                  }
                }
              }
            },
            "404": {
              "description": "Execution not found"
            }
          }
        }
      },
      "/core/executions": {
        "get": {
          "tags": [
            "Core Execution"
          ],
          "summary": "List all executions — optionally filter by status",
          "parameters": [
            {
              "name": "status",
              "in": "query",
              "schema": {
                "type": "string",
                "enum": [
                  "received",
                  "running",
                  "completed",
                  "failed"
                ]
              }
            }
          ],
          "responses": {
            "200": {
              "description": "Array of execution summaries"
            }
          }
        }
      },
      "/core/telemetry/{id}": {
        "get": {
          "tags": [
            "Core Execution"
          ],
          "summary": "Get telemetry events for a specific execution",
          "parameters": [
            {
              "name": "id",
              "in": "path",
              "required": true,
              "schema": {
                "type": "string"
              }
            }
          ],
          "responses": {
            "200": {
              "description": "Telemetry events array"
            },
            "404": {
              "description": "No telemetry found"
            }
          }
        }
      },
      "/core/telemetry": {
        "get": {
          "tags": [
            "Core Execution"
          ],
          "summary": "Get all execution telemetry",
          "responses": {
            "200": {
              "description": "All telemetry events"
            }
          }
        }
      },
      "/core/game-state/{sessionId}": {
        "get": {
          "tags": [
            "Game State"
          ],
          "summary": "Get live in-memory game state for a session",
          "description": "Updated in real-time by runtime_event socket messages from the engine.",
          "parameters": [
            {
              "name": "sessionId",
              "in": "path",
              "required": true,
              "schema": {
                "type": "string"
              }
            }
          ],
          "responses": {
            "200": {
              "description": "Current game state"
            },
            "404": {
              "description": "Session not found"
            }
          }
        }
      },
      "/core/game-sessions": {
        "get": {
          "tags": [
            "Game State"
          ],
          "summary": "List all active game session IDs",
          "responses": {
            "200": {
              "description": "Array of active session IDs"
            }
          }
        }
      },
      "/core/game-state/{sessionId}/replay": {
        "get": {
          "tags": [
            "Game State"
          ],
          "summary": "Deterministic replay of a session from bucket event trace",
          "parameters": [
            {
              "name": "sessionId",
              "in": "path",
              "required": true,
              "schema": {
                "type": "string"
              }
            }
          ],
          "responses": {
            "200": {
              "description": "Reconstructed state"
            },
            "500": {
              "description": "Replay error"
            }
          }
        }
      },
      "/execute": {
        "post": {
          "tags": [
            "Execution Interface"
          ],
          "summary": "Phase 4 hardened entry point — engineExecutionContract_v3",
          "description": "Strict validation: headers AND body fields must match.\nRequired headers: `X-Trace-Id`, `X-Execution-Id`\nValid game_mode: `runner` | `sidescroller` | `open_scene`\nentities must be non-empty array.\nphysics.gravity must be [x,y,z] array.\nscoring.rules required.",
          "parameters": [
            {
              "name": "X-Trace-Id",
              "in": "header",
              "required": true,
              "schema": {
                "type": "string"
              }
            },
            {
              "name": "X-Execution-Id",
              "in": "header",
              "required": true,
              "schema": {
                "type": "string"
              }
            }
          ],
          "requestBody": {
            "required": true,
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "required": [
                    "execution_id",
                    "trace_id",
                    "game_mode",
                    "entities",
                    "physics",
                    "scoring"
                  ],
                  "properties": {
                    "execution_id": {
                      "type": "string"
                    },
                    "trace_id": {
                      "type": "string"
                    },
                    "game_mode": {
                      "type": "string",
                      "enum": [
                        "runner",
                        "sidescroller",
                        "open_scene"
                      ]
                    },
                    "entities": {
                      "type": "array",
                      "minItems": 1,
                      "items": {
                        "type": "object"
                      }
                    },
                    "physics": {
                      "type": "object",
                      "required": [
                        "gravity"
                      ],
                      "properties": {
                        "gravity": {
                          "type": "array",
                          "items": {
                            "type": "number"
                          },
                          "example": [
                            0,
                            -9.8,
                            0
                          ]
                        }
                      }
                    },
                    "scoring": {
                      "type": "object",
                      "required": [
                        "rules"
                      ],
                      "properties": {
                        "rules": {
                          "type": "object"
                        }
                      }
                    }
                  }
                }
              }
            }
          },
          "responses": {
            "200": {
              "description": "Contract accepted",
              "content": {
                "application/json": {
                  "schema": {
                    "type": "object",
                    "properties": {
                      "status": {
                        "type": "string",
                        "example": "accepted"
                      },
                      "trace_id": {
                        "type": "string"
                      },
                      "execution_id": {
                        "type": "string"
                      },
                      "accepted_at": {
                        "type": "number"
                      }
                    }
                  }
                }
              }
            },
            "400": {
              "description": "Rejected — missing headers, field mismatch, invalid game_mode, empty entities, missing gravity or scoring.rules"
            }
          }
        }
      },
      "/api/tts/speak": {
        "post": {
          "tags": [
            "TTS"
          ],
          "summary": "Convert text to speech — returns audio/mpeg stream",
          "description": "Translates to target language via Google Translate then generates MP3 via node-gtts. 3s timeout on translation, falls back to original text.",
          "requestBody": {
            "required": true,
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "required": [
                    "text"
                  ],
                  "properties": {
                    "text": {
                      "type": "string",
                      "example": "Game started. Good luck!"
                    },
                    "language": {
                      "type": "string",
                      "default": "en",
                      "example": "en",
                      "description": "BCP-47 code: en, hi, fr, de, etc."
                    }
                  }
                }
              }
            }
          },
          "responses": {
            "200": {
              "description": "MP3 audio stream",
              "content": {
                "audio/mpeg": {
                  "schema": {
                    "type": "string",
                    "format": "binary"
                  }
                }
              }
            },
            "400": {
              "description": "Text is required"
            },
            "500": {
              "description": "TTS generation failed"
            }
          }
        }
      },
      "/pipeline/run": {
        "post": {
          "tags": [
            "Pipeline"
          ],
          "summary": "Run maritime governance pipeline for a vessel signal",
          "description": "Full 5-stage pipeline: contract → Mitra decision → enforcement gate → event collection → bucket write.",
          "requestBody": {
            "required": true,
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "required": [
                    "vessel_id",
                    "lat",
                    "lon",
                    "speed",
                    "heading"
                  ],
                  "properties": {
                    "vessel_id": {
                      "type": "string",
                      "example": "vessel_001"
                    },
                    "lat": {
                      "type": "number",
                      "example": 25
                    },
                    "lon": {
                      "type": "number",
                      "example": 55
                    },
                    "speed": {
                      "type": "number",
                      "example": 12.5
                    },
                    "heading": {
                      "type": "number",
                      "example": 180
                    },
                    "status": {
                      "type": "string",
                      "default": "moving"
                    },
                    "trace_id": {
                      "type": "string"
                    },
                    "execution_id": {
                      "type": "string"
                    }
                  }
                }
              }
            }
          },
          "responses": {
            "200": {
              "description": "Pipeline result with decision ALLOW/BLOCK/FLAG"
            },
            "400": {
              "description": "Missing required fields"
            },
            "422": {
              "description": "Enforcement failure"
            },
            "500": {
              "description": "Pipeline crash"
            }
          }
        }
      },
      "/pipeline/result/{trace_id}": {
        "get": {
          "tags": [
            "Pipeline"
          ],
          "summary": "Get all 5 artifacts for a completed pipeline execution",
          "description": "Returns: schema, decision, events, state, log",
          "parameters": [
            {
              "name": "trace_id",
              "in": "path",
              "required": true,
              "schema": {
                "type": "string"
              }
            }
          ],
          "responses": {
            "200": {
              "description": "All artifacts keyed by type"
            },
            "404": {
              "description": "No artifacts found"
            },
            "500": {
              "description": "Artifact read error"
            }
          }
        }
      },
      "/pipeline/replay/{trace_id}": {
        "post": {
          "tags": [
            "Pipeline"
          ],
          "summary": "Replay a pipeline execution from stored artifacts",
          "parameters": [
            {
              "name": "trace_id",
              "in": "path",
              "required": true,
              "schema": {
                "type": "string"
              }
            }
          ],
          "responses": {
            "200": {
              "description": "Replay result"
            },
            "422": {
              "description": "Replay failed"
            }
          }
        }
      },
      "/pipeline/health": {
        "get": {
          "tags": [
            "Pipeline"
          ],
          "summary": "Pipeline service health check",
          "responses": {
            "200": {
              "description": "Health status",
              "content": {
                "application/json": {
                  "schema": {
                    "type": "object",
                    "properties": {
                      "success": {
                        "type": "boolean"
                      },
                      "service": {
                        "type": "string",
                        "example": "pipeline"
                      },
                      "status": {
                        "type": "string",
                        "example": "ok"
                      },
                      "bucket_accessible": {
                        "type": "boolean"
                      },
                      "artifact_count": {
                        "type": "integer"
                      },
                      "checked_at": {
                        "type": "number"
                      }
                    }
                  }
                }
              }
            }
          }
        }
      },
      "/pipeline/telemetry/{trace_id}": {
        "get": {
          "tags": [
            "Pipeline"
          ],
          "summary": "Get telemetry events for a pipeline trace — optionally filter by stage",
          "parameters": [
            {
              "name": "trace_id",
              "in": "path",
              "required": true,
              "schema": {
                "type": "string"
              }
            },
            {
              "name": "stage",
              "in": "query",
              "schema": {
                "type": "string"
              },
              "description": "Filter by stage name (e.g. decision_received)"
            }
          ],
          "responses": {
            "200": {
              "description": "Telemetry events for the trace"
            },
            "400": {
              "description": "Unknown stage filter"
            },
            "404": {
              "description": "No telemetry found"
            },
            "500": {
              "description": "Trace consistency violation"
            }
          }
        }
      },
      "/simulate/run": {
        "post": {
          "tags": [
            "Simulation"
          ],
          "summary": "Run a deterministic SumScript simulation (idempotent by trace_id)",
          "description": "Validates against simulationContract.v1, adapts to SumScript, runs ticks.\nIdempotent: same trace_id returns stored result without re-running.\nFail-closed: any contract violation → 422, no partial execution.\nMax body size: 256KB.",
          "requestBody": {
            "required": true,
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "required": [
                    "trace_id",
                    "execution_id",
                    "domain",
                    "scenario",
                    "entities",
                    "behaviors",
                    "rules",
                    "constraints"
                  ],
                  "properties": {
                    "trace_id": {
                      "type": "string",
                      "example": "trace_sim_001"
                    },
                    "execution_id": {
                      "type": "string",
                      "example": "exec_sim_001"
                    },
                    "domain": {
                      "type": "string",
                      "example": "runner"
                    },
                    "scenario": {
                      "type": "string",
                      "example": "obstacle_course"
                    },
                    "entities": {
                      "type": "array",
                      "items": {
                        "type": "object"
                      }
                    },
                    "behaviors": {
                      "type": "array",
                      "items": {
                        "type": "object"
                      }
                    },
                    "rules": {
                      "type": "array",
                      "items": {
                        "type": "object"
                      }
                    },
                    "constraints": {
                      "type": "object"
                    },
                    "ticks": {
                      "type": "integer",
                      "default": 10,
                      "example": 10
                    }
                  }
                }
              }
            }
          },
          "responses": {
            "200": {
              "description": "Simulation completed — returns simulationState.v1"
            },
            "413": {
              "description": "Request body exceeds 256KB limit"
            },
            "422": {
              "description": "Contract validation failed or simulation error"
            }
          }
        }
      },
      "/simulate/replay/{trace_id}": {
        "post": {
          "tags": [
            "Simulation"
          ],
          "summary": "Replay a simulation from stored contract — validates determinism",
          "description": "Same trace_id → same seed → identical output guaranteed.",
          "parameters": [
            {
              "name": "trace_id",
              "in": "path",
              "required": true,
              "schema": {
                "type": "string"
              }
            }
          ],
          "responses": {
            "200": {
              "description": "Replay result matching original run"
            },
            "400": {
              "description": "trace_id required"
            },
            "422": {
              "description": "Replay failed or determinism violation"
            }
          }
        }
      },
      "/simulate/result/{trace_id}": {
        "get": {
          "tags": [
            "Simulation"
          ],
          "summary": "Get stored simulation result by trace_id",
          "parameters": [
            {
              "name": "trace_id",
              "in": "path",
              "required": true,
              "schema": {
                "type": "string"
              }
            }
          ],
          "responses": {
            "200": {
              "description": "simulationState.v1 result object"
            },
            "404": {
              "description": "No result found for trace_id"
            }
          }
        }
      },
      "/simulate/health": {
        "get": {
          "tags": [
            "Simulation"
          ],
          "summary": "Simulation node health check",
          "responses": {
            "200": {
              "description": "Health status",
              "content": {
                "application/json": {
                  "schema": {
                    "type": "object",
                    "properties": {
                      "status": {
                        "type": "string",
                        "example": "ok"
                      },
                      "node": {
                        "type": "string",
                        "example": "simulation"
                      },
                      "headless": {
                        "type": "boolean",
                        "example": true
                      },
                      "ui_required": {
                        "type": "boolean",
                        "example": false
                      },
                      "stored_count": {
                        "type": "integer"
                      },
                      "timestamp": {
                        "type": "number"
                      }
                    }
                  }
                }
              }
            }
          }
        }
      },
      "/socket.io/dashboard": {
        "get": {
          "tags": [
            "Socket.IO — Dashboard"
          ],
          "summary": "⚡ Default namespace `/` — connect with Bearer JWT",
          "description": "**Connect:** `io(\"http://localhost:3000\", { auth: { token } })`\n\n### Client → Server events\n| Event | Payload | Description |\n|---|---|---|\n| `action` | `{ type, payload, ts, nonce, sig }` | Send HMAC-signed user action |\n| `presence` | `\"active\" | \"idle\"` | Update own presence state |\n| `agent_heartbeat` | `{ agentId, timestamp, nonce, sig }` | Secure agent heartbeat |\n| `get_engine_status` | _(none)_ | Request current engine status |\n| `get_game_state` | `{ sessionId }` | Request live game state snapshot |\n\n### Server → Client events\n| Event | Payload | Description |\n|---|---|---|\n| `auth_context` | `{ userId, role, isSimulated }` | Sent on connect — identity confirmation |\n| `agent_nonce` | `{ [agentId]: nonce }` | Initial nonce map for all agents |\n| `presence_update` | `{ [userId]: presenceObj }` | Connected users with state (admin sees all) |\n| `action_error` | `{ error: \"timestamp_expired\" | \"invalid_signature\" | \"replay_detected\" }` | Action rejected |\n| `agent_heartbeat_result` | `{ ok, reason? }` | Heartbeat accepted/rejected |\n| `agent_update` | `{ agentId, state, message }` | Agent FSM reaction |\n| `nav_idle_prompt` | `{ userId }` | NavAgent idle trigger |\n| `job_status` | `{ jobId, jobType, status, priority, submittedAt, executionId }` | Job queue update |\n| `engine_status` | `{ connected, lastHeartbeat, ... }` | Engine connection state |\n| `engine_telemetry` | `{ event, jobId, ... }` | Engine telemetry broadcast |\n| `game:started` | `{ game_mode, sessionId, execution_id, trace_id }` | Game session started |\n| `game:ended` | `{ reason, final_score, sessionId }` | Game session ended |\n| `game_state_snapshot` | `{ sessionId, state }` | Response to get_game_state |\n| `game_state_update` | `{ sessionId, state, changes, event_type }` | Live state delta from runtime_event |\n| `sim_result` | `{ trace_id, execution_id, game_mode, simResult, nicai, samruddhi }` | SimEngine result |\n| `telemetry` | `{ fps, score, lives, trace_id, execution_id }` | Game telemetry from engine |\n| `execution:started` | `{ execution_id, trace_id, timestamp }` | Execution dispatched |\n| `execution:completed` | `{ execution_id, trace_id, duration, timestamp }` | Execution done |\n| `execution:failed` | `{ execution_id, trace_id, error, timestamp }` | Execution failed |\n| `execution:retry` | `{ execution_id, attempt }` | Execution retry triggered |",
          "responses": {
            "200": {
              "description": "WebSocket upgrade — see description for event protocol"
            }
          }
        }
      },
      "/socket.io/engine": {
        "get": {
          "tags": [
            "Socket.IO — Engine"
          ],
          "summary": "⚡ Namespace `/engine` — engine authenticates with engine JWT",
          "description": "**Connect:** `io(\"http://localhost:3000/engine\", { auth: { token: engineToken } })`\nJWT must have `role: \"engine\"`. Obtain via `GET /auth/engine-token`.\n\n### Engine → Server events (all require HMAC signature + nonce)\n| Event | Payload | Description |\n|---|---|---|\n| `engine_ready` | _(none)_ | Engine signals it is ready to receive jobs |\n| `engine_heartbeat` | _(none)_ | Keep-alive — must arrive every <10s or engine is disconnected |\n| `job_ack` | `{ payload: { jobId, status }, sig, nonce }` | Acknowledge job received |\n| `job_status` | `{ payload: { jobId, jobType, status, error }, sig, nonce }` | Job status update |\n| `job_started` | `{ payload: { job_id, timestamp }, sig, nonce }` | Job execution started |\n| `job_progress` | `{ payload: { job_id, progress, timestamp }, sig, nonce }` | Job progress 0–100 |\n| `job_completed` | `{ payload: { job_id, result, timestamp }, sig, nonce }` | Job finished |\n| `job_failed` | `{ payload: { job_id, error, details, timestamp }, sig, nonce }` | Job failed |\n| `engine_error` | `{ payload: { error, details }, sig, nonce }` | Engine-side error report |\n| `telemetry` | `{ fps, score, lives, trace_id, execution_id }` | Live game telemetry |\n| `game:started` | `{ game_mode, sessionId, execution_id, trace_id, gameplay_contract }` | Game session started |\n| `game:ended` | `{ reason, final_score, sessionId }` | Game session ended |\n| `runtime_event` | `{ sessionId, event }` | Gameplay state event (collision, pickup, etc.) |\n\n### Server → Engine events\n| Event | Payload | Description |\n|---|---|---|\n| `job:dispatch` | `{ job_id, job_type, gameplay_contract, payload, execution_params, submitted_at, user_id }` | Dispatch job |\n| `ready_ack` | `{ status: \"acknowledged\", ts }` | Response to engine_ready |\n| `heartbeat_ack` | `{ ts }` | Response to engine_heartbeat |\n| `ack_received` | `{ jobId, ts }` | Response to job_ack |\n| `status_ack` | `{ jobId, received, ts }` | Response to job_status |\n| `status_rejected` | `{ reason }` | job_status failed signature/nonce check |\n| `error_ack` | `{ received, ts }` | Response to engine_error |\n| `event_rejected` | `{ reason }` | runtime_event blocked by integrity guard |",
          "responses": {
            "200": {
              "description": "WebSocket upgrade — see description for event protocol"
            }
          }
        }
      },
      "/socket.io/simulate-stream": {
        "get": {
          "tags": [
            "Socket.IO — Sim Stream"
          ],
          "summary": "⚡ Namespace `/simulate/stream` — real-time simulation tick streaming",
          "description": "**Connect:** `io(\"http://localhost:3000/simulate/stream\")`\n\n### Client → Server events\n| Event | Payload | Description |\n|---|---|---|\n| `stream:start` | `{ contract }` | Start streaming simulation (simulationContract.v1) |\n| `replay:start` | `{ trace_id }` | Replay stored simulation as stream |\n\n### Server → Client events\n| Event | Payload | Description |\n|---|---|---|\n| `stream:tick` | TANTRA delta payload | One tick of simulation state |\n| `stream:done` | `{ trace_id, ticks_run, status }` | Stream completed |\n| `stream:error` | `{ code, reason, trace_id }` | Error (INVALID_CONTRACT, STREAM_ALREADY_ACTIVE, ADAPT_FAILED, REPLAY_ALREADY_ACTIVE, MISSING_TRACE_ID) |",
          "responses": {
            "200": {
              "description": "WebSocket upgrade — see description for event protocol"
            }
          }
        }
      }
    }
  },
  "customOptions": {}
};
  url = options.swaggerUrl || url
  var urls = options.swaggerUrls
  var customOptions = options.customOptions
  var spec1 = options.swaggerDoc
  var swaggerOptions = {
    spec: spec1,
    url: url,
    urls: urls,
    dom_id: '#swagger-ui',
    deepLinking: true,
    presets: [
      SwaggerUIBundle.presets.apis,
      SwaggerUIStandalonePreset
    ],
    plugins: [
      SwaggerUIBundle.plugins.DownloadUrl
    ],
    layout: "StandaloneLayout"
  }
  for (var attrname in customOptions) {
    swaggerOptions[attrname] = customOptions[attrname];
  }
  var ui = SwaggerUIBundle(swaggerOptions)

  if (customOptions.oauth) {
    ui.initOAuth(customOptions.oauth)
  }

  if (customOptions.preauthorizeApiKey) {
    const key = customOptions.preauthorizeApiKey.authDefinitionKey;
    const value = customOptions.preauthorizeApiKey.apiKeyValue;
    if (!!key && !!value) {
      const pid = setInterval(() => {
        const authorized = ui.preauthorizeApiKey(key, value);
        if(!!authorized) clearInterval(pid);
      }, 500)

    }
  }

  if (customOptions.authAction) {
    ui.authActions.authorize(customOptions.authAction)
  }

  window.ui = ui
}
