FROM public.ecr.aws/lambda/python:3.13

WORKDIR ${LAMBDA_TASK_ROOT}

COPY infra/docker/lambda/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

COPY data/ ./data/

ENV PYTHONPATH="${LAMBDA_TASK_ROOT}/src"

COPY infra/docker/lambda/app.py ./app.py


CMD ["app.lambda_handler"]

