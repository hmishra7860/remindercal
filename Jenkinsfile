// Required Jenkins Credentials (Manage Jenkins -> Credentials -> Global):
// 1. registry-credentials  (Username with password) -> Docker Hub / Registry login
// 2. k3s-kubeconfig        (Secret file)            -> K3s cluster kubeconfig
// 3. remindercal-env       (Secret file)            -> Production .env file for K8s secrets

pipeline {
    agent {
        label 'ubuntu'
    }

    parameters {
        string(name: 'REGISTRY', defaultValue: 'docker.io/YOUR_USER', description: 'Registry path (e.g. docker.io/username)')
        booleanParam(name: 'DEPLOY_MONITORING', defaultValue: true, description: 'Deploy Prometheus & Grafana stack')
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 20, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    environment {
        K8S_NAMESPACE  = 'remindercal'
        IMAGE_TAG      = "${env.BUILD_NUMBER}-${env.GIT_COMMIT.take(7)}"
        BACKEND_IMAGE  = "${params.REGISTRY}/remindercal-backend:${IMAGE_TAG}"
        FRONTEND_IMAGE = "${params.REGISTRY}/remindercal-frontend:${IMAGE_TAG}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build Docker Images') {
            steps {
                sh '''
                    docker build -t "$BACKEND_IMAGE" ./backend
                    docker build -t "$FRONTEND_IMAGE" -f nginx/Dockerfile .
                '''
            }
        }

        stage('Smoke Test Application') {
            steps {
                // 1. Backend: Run tests directly inside the already-built image (no extra pip install needed)
                sh '''
                    docker run --rm \
                        -e SCHEDULER_ENABLED=false \
                        -e SECRET_KEY=ci-test-key \
                        "$BACKEND_IMAGE" sh -ec '
                            python -m compileall -q app alembic
                            python -c "from app.main import app; print(\\"FastAPI App Loaded:\\", app.title)"
                            [ "$(alembic heads | grep -c "(head)")" -eq 1 ]
                        '
                '''
                // 2. Frontend: Check JS syntax
                sh '''
                    docker run --rm -v "$WORKSPACE/frontend:/src:ro" node:20-alpine sh -ec '
                        for f in /src/sw.js /src/js/*.js; do node --check "$f"; done
                    '
                '''
            }
        }

        stage('Push Docker Images') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'docker-registry-creds', usernameVariable: 'REG_USER', passwordVariable: 'REG_PASS')]) {
                    sh '''
                        echo "$REG_PASS" | docker login -u "$REG_USER" --password-stdin
                        docker push "$BACKEND_IMAGE"
                        docker push "$FRONTEND_IMAGE"
                    '''
                }
            }
            post {
                always { sh 'docker logout || true' }
            }
        }

        stage('Deploy to K3s') {
            agent {
                label 'Linux'
            }
            steps {
                withCredentials([
                    file(credentialsId: 'k3s-kubeconfig', variable: 'KUBECONFIG'),
                    file(credentialsId: 'remindercal-env', variable: 'ENV_FILE')
                ]) {
                    sh '''
                        # 1. Apply namespace & config (Ensure placeholder Secret is removed from 00-namespace-config.yaml)
                        kubectl apply -f k8s/00-namespace-config.yaml

                        # 2. Inject secrets directly from the uploaded Jenkins Secret File
                        kubectl -n "$K8S_NAMESPACE" create secret generic remindercal-secrets \
                            --from-env-file="$ENV_FILE" --dry-run=client -o yaml | kubectl apply -f -

                        # 3. Deploy Database, Backend, and Frontend
                        kubectl apply -f k8s/10-postgres.yaml -f k8s/20-backend.yaml -f k8s/30-frontend-ingress.yaml

                        # 4. Update deployments with the newly built image tags
                        kubectl -n "$K8S_NAMESPACE" set image deployment/backend backend="$BACKEND_IMAGE"
                        kubectl -n "$K8S_NAMESPACE" set image deployment/frontend nginx="$FRONTEND_IMAGE"

                        # 5. Wait for rollouts to finish
                        kubectl -n "$K8S_NAMESPACE" rollout status statefulset/postgres --timeout=120s
                        kubectl -n "$K8S_NAMESPACE" rollout status deployment/backend deployment/frontend --timeout=180s

                        # 6. Optional Infrastructure Monitoring
                        if [ "$DEPLOY_MONITORING" = "true" ]; then
                            kubectl apply -f k8s/40-monitoring.yaml
                            kubectl -n monitoring rollout status deployment/prometheus deployment/grafana --timeout=120s
                        fi
                    '''
                }
            }
            post {
                failure {
                    withCredentials([file(credentialsId: 'k3s-kubeconfig', variable: 'KUBECONFIG')]) {
                        sh '''
                            kubectl -n "$K8S_NAMESPACE" get pods -o wide || true
                            kubectl -n "$K8S_NAMESPACE" logs deployment/backend --tail=50 || true
                        '''
                    }
                }
                success {
                    echo "Deployment successful! Access your app at: http://<your-k3s-node-ip>/"
                }
            }
        }
    }
}