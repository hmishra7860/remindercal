// ReminderCal CI/CD: git checkout -> test -> docker build & push -> deploy to k3s.
//
// Runs on a Jenkins agent that has: git, docker, kubectl (and network access to the k3s API).
// Labelled "k3s" by default; change `agent { label ... }` to match your setup.
//
// Jenkins global credentials required (Manage Jenkins -> Credentials -> Global):
//   ID                          Kind                      Used for
//   --------------------------  ------------------------  ------------------------------------------
//   registry-credentials        Username with password    docker login / push, and k3s image pull secret
//   k3s-kubeconfig              Secret file               kubeconfig for the k3s cluster
//   remindercal-secret-key      Secret text               SECRET_KEY (JWT + SMTP-password encryption)
//   remindercal-postgres-pass   Secret text               POSTGRES_PASSWORD (+ built into DATABASE_URL)
//   remindercal-vapid-public    Secret text               VAPID_PUBLIC_KEY   (web push; may be empty)
//   remindercal-vapid-private   Secret text               VAPID_PRIVATE_KEY  (web push; may be empty)
//   remindercal-inbound-secret  Secret text               INBOUND_WEBHOOK_SECRET (may be empty)
//   remindercal-git-credentials Username with password    (optional) only for private Git repos
//
// Secrets never live in the repo: the placeholder Secret in k8s/00-namespace-config.yaml is
// skipped and the real `remindercal-secrets` Secret is created from the credentials above.

pipeline {
    agent { label 'k3s' }

    parameters {
        string(name: 'GIT_URL',            defaultValue: 'https://github.com/YOUR_ORG/remindercal.git', description: 'Git repository URL')
        string(name: 'GIT_BRANCH',         defaultValue: 'main',                 description: 'Branch to build')
        string(name: 'REGISTRY',           defaultValue: 'docker.io',            description: 'Container registry host')
        string(name: 'REGISTRY_NAMESPACE', defaultValue: 'YOUR_REGISTRY_USER',   description: 'Registry user / org the images are pushed under')
        string(name: 'APP_DOMAIN',         defaultValue: 'remindercal.example.com', description: 'Public host name (Ingress, PUBLIC_BASE_URL, CORS, INBOUND_DOMAIN)')
        string(name: 'ADMIN_EMAIL',        defaultValue: 'admin@example.com',    description: 'Used for VAPID_SUBJECT (mailto:)')
        booleanParam(name: 'DEPLOY_MONITORING', defaultValue: false,             description: 'Also apply k8s/40-monitoring.yaml')
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    environment {
        K8S_NAMESPACE = 'remindercal'
        PG_USER       = 'remindercal'
        PG_DB         = 'remindercal'
        PY_IMAGE      = 'python:3.12-slim'
    }

    stages {

        stage('Checkout') {
            steps {
                script {
                    def gitArgs = [url: params.GIT_URL, branch: params.GIT_BRANCH]
                    // Public repo: no credentials needed. For a private repo, create the
                    // 'remindercal-git-credentials' credential and uncomment the next line.
                    // gitArgs.credentialsId = 'remindercal-git-credentials'
                    git(gitArgs)

                    def sha = sh(script: 'git rev-parse --short=8 HEAD', returnStdout: true).trim()
                    env.IMAGE_TAG = "${env.BUILD_NUMBER}-${sha}"
                    env.IMAGE_BASE = "${params.REGISTRY}/${params.REGISTRY_NAMESPACE}"
                    env.BACKEND_IMAGE  = "${env.IMAGE_BASE}/remindercal-backend:${env.IMAGE_TAG}"
                    env.FRONTEND_IMAGE = "${env.IMAGE_BASE}/remindercal-frontend:${env.IMAGE_TAG}"
                    currentBuild.displayName = "#${env.BUILD_NUMBER} ${sha}"
                }
            }
        }

        stage('Test') {
            steps {
                // The repo ships no test suite yet, so this stage does what can be verified
                // without a database: byte-compile, import the FastAPI app, check the OpenAPI
                // schema builds, make sure Alembic has a single head, and run pytest if a
                // backend/tests directory exists. Everything runs in a throwaway container.
                sh '''
                    docker run --rm \
                        -v "$WORKSPACE/backend:/src:ro" \
                        -e PYTHONDONTWRITEBYTECODE=1 \
                        -e PIP_NO_CACHE_DIR=1 \
                        -e SCHEDULER_ENABLED=false \
                        -e SECRET_KEY=ci-test-key \
                        "$PY_IMAGE" sh -ec '
                            cp -r /src /app && cd /app
                            pip install -q -r requirements.txt pytest
                            python -m compileall -q app alembic
                            python - <<PY
                            from fastapi.testclient import TestClient
                            from app.main import app
                            c = TestClient(app)                       # no lifespan => no DB / scheduler needed
                            r = c.get("/openapi.json")
                            assert r.status_code == 200, r.text
                            print("OpenAPI OK:", len(r.json()["paths"]), "paths")
                            PY
                            heads=$(alembic heads | grep -c "(head)")
                            [ "$heads" -eq 1 ] || { echo "Expected exactly 1 Alembic head, found $heads"; exit 1; }
                            if [ -d tests ]; then pytest -q; else echo "No backend/tests directory - skipping pytest"; fi
                        '
                '''
                // Frontend: syntax-check every JS file (also catches a broken service worker).
                sh '''
                    docker run --rm -v "$WORKSPACE/frontend:/src:ro" node:20-alpine sh -ec '
                        for f in /src/sw.js /src/js/*.js; do node --check "$f"; done
                    '
                '''
            }
        }

        stage('Build Docker Images') {
            steps {
                sh '''
                    docker build -t "$BACKEND_IMAGE"  ./backend
                    docker build -t "$FRONTEND_IMAGE" -f nginx/Dockerfile .
                '''
            }
        }

        stage('Push Docker Images') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'registry-credentials',usernameVariable: 'REG_USER',passwordVariable: 'REG_PASS')]) 
                {
                    sh '''
                        echo "$REG_PASS" | docker login "$REGISTRY" -u "$REG_USER" --password-stdin
                        docker push "$BACKEND_IMAGE"
                        docker push "$FRONTEND_IMAGE"
                        # Moving "latest" tags for convenience; deployments use the immutable tag.
                        docker tag "$BACKEND_IMAGE"  "$IMAGE_BASE/remindercal-backend:latest"
                        docker tag "$FRONTEND_IMAGE" "$IMAGE_BASE/remindercal-frontend:latest"
                        docker push "$IMAGE_BASE/remindercal-backend:latest"
                        docker push "$IMAGE_BASE/remindercal-frontend:latest"
                    '''
                }
            }
            post {
                always { sh 'docker logout "$REGISTRY" || true' }
            }
        }

        stage('Deploy to k3s') {
            steps {
                withCredentials([
                    file(credentialsId: 'k3s-kubeconfig', variable: 'KUBECONFIG'),
                    usernamePassword(credentialsId: 'registry-credentials',
                                     usernameVariable: 'REG_USER', passwordVariable: 'REG_PASS'),
                    string(credentialsId: 'remindercal-secret-key',     variable: 'APP_SECRET_KEY'),
                    string(credentialsId: 'remindercal-postgres-pass',  variable: 'APP_PG_PASS'),
                    string(credentialsId: 'remindercal-vapid-public',   variable: 'APP_VAPID_PUBLIC'),
                    string(credentialsId: 'remindercal-vapid-private',  variable: 'APP_VAPID_PRIVATE'),
                    string(credentialsId: 'remindercal-inbound-secret', variable: 'APP_INBOUND_SECRET')
                ]) {
                    // Single-quoted on purpose: secrets are expanded by the shell, never by
                    // Groovy, so they are not interpolated into the build log or script text.
                    sh '''
                        set +x
                        R="$WORKSPACE/.rendered"
                        rm -rf "$R" && mkdir -p "$R"

                        # --- 1. Render manifests (image tags, domain, admin e-mail) -------------
                        # Drop the placeholder Secret document: the real one is created in step 3.
                        awk 'BEGIN{RS="\\n---\\n"; ORS="\\n---\\n"} !/(^|\\n)kind: Secret/' \
                            k8s/00-namespace-config.yaml > "$R/00-namespace-config.yaml"

                        cp k8s/10-postgres.yaml k8s/20-backend.yaml k8s/30-frontend-ingress.yaml k8s/40-monitoring.yaml "$R/"

                        sed -i \
                            -e "s|remindercal-backend:latest|$BACKEND_IMAGE|g" \
                            -e "s|remindercal-frontend:latest|$FRONTEND_IMAGE|g" \
                            -e "s|remindercal\\.example\\.com|$APP_DOMAIN|g" \
                            -e "s|mailto:admin@example\\.com|mailto:$ADMIN_EMAIL|g" \
                            "$R"/*.yaml

                        # --- 2. Namespace + config ------------------------------------------------
                        kubectl apply -f "$R/00-namespace-config.yaml"

                        # --- 3. Secrets from Jenkins credentials ----------------------------------
                        # URL-encode the DB password so any character is safe inside DATABASE_URL.
                        ENC_PASS=$(P="$APP_PG_PASS" docker run --rm -e P "$PY_IMAGE" \
                            python -c 'import os,urllib.parse as u; print(u.quote(os.environ["P"], safe=""))')

                        umask 077
                        ENVFILE="$R/secrets.env"
                        {
                            printf 'POSTGRES_USER=%s\\n'          "$PG_USER"
                            printf 'POSTGRES_PASSWORD=%s\\n'      "$APP_PG_PASS"
                            printf 'POSTGRES_DB=%s\\n'            "$PG_DB"
                            printf 'DATABASE_URL=postgresql+asyncpg://%s:%s@postgres:5432/%s\\n' "$PG_USER" "$ENC_PASS" "$PG_DB"
                            printf 'SECRET_KEY=%s\\n'             "$APP_SECRET_KEY"
                            printf 'VAPID_PUBLIC_KEY=%s\\n'       "$APP_VAPID_PUBLIC"
                            printf 'VAPID_PRIVATE_KEY=%s\\n'      "$APP_VAPID_PRIVATE"
                            printf 'INBOUND_WEBHOOK_SECRET=%s\\n' "$APP_INBOUND_SECRET"
                        } > "$ENVFILE"

                        kubectl -n "$K8S_NAMESPACE" create secret generic remindercal-secrets \
                            --from-env-file="$ENVFILE" --dry-run=client -o yaml | kubectl apply -f -
                        rm -f "$ENVFILE"

                        # Registry pull secret, attached to the namespace's default service account.
                        kubectl -n "$K8S_NAMESPACE" create secret docker-registry regcred \
                            --docker-server="$REGISTRY" --docker-username="$REG_USER" \
                            --docker-password="$REG_PASS" --dry-run=client -o yaml | kubectl apply -f -
                        kubectl -n "$K8S_NAMESPACE" patch serviceaccount default \
                            -p '{"imagePullSecrets":[{"name":"regcred"}]}'

                        # --- 4. Workloads ---------------------------------------------------------
                        set -x
                        kubectl apply -f "$R/10-postgres.yaml"
                        kubectl -n "$K8S_NAMESPACE" rollout status statefulset/postgres --timeout=180s

                        kubectl apply -f "$R/20-backend.yaml" -f "$R/30-frontend-ingress.yaml"
                        kubectl -n "$K8S_NAMESPACE" rollout status deployment/backend  --timeout=300s
                        kubectl -n "$K8S_NAMESPACE" rollout status deployment/frontend --timeout=180s

                        if [ "$DEPLOY_MONITORING" = "true" ]; then
                            kubectl apply -f "$R/40-monitoring.yaml"
                        fi
                    '''
                }
            }
            post {
                failure {
                    withCredentials([file(credentialsId: 'k3s-kubeconfig', variable: 'KUBECONFIG')]) {
                        sh '''
                            kubectl -n "$K8S_NAMESPACE" get pods -o wide || true
                            kubectl -n "$K8S_NAMESPACE" logs deployment/backend --tail=100 || true
                        '''
                    }
                }
                cleanup { sh 'rm -rf "$WORKSPACE/.rendered"' }
            }
        }
    }

    post {
        success { echo "Deployed ${env.BACKEND_IMAGE} and ${env.FRONTEND_IMAGE} to https://${params.APP_DOMAIN}" }
        failure { echo 'Pipeline failed - see the stage logs above.' }
    }
}
