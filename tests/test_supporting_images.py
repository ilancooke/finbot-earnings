from dataclasses import replace
from io import BytesIO

import boto3
from botocore.stub import ANY, Stubber
from PIL import Image
import pytest

from finbot_earnings.processing.aws_adapters import NovaLiteModel, NOVA_LITE_MODEL_ID, NOVA_PROMPT_VERSION
from finbot_earnings.processing.contracts import FilingReady
from finbot_earnings.processing.domain import Document, ExtractionConfig, ModelRequest
from finbot_earnings.processing.errors import InputReview
from finbot_earnings.processing.pipeline import FilingPipeline
from finbot_earnings.processing.sqlite_store import SQLiteProcessingRepository
from tests.processing_helpers import fixture, rehash, Documents, Model, Publisher


def image_fixture():
    payload, bodies, response = fixture()
    output = BytesIO()
    Image.new('RGB', (32, 32), 'white').save(output, format='PNG')
    reference = dict(artifact_id=payload['filing_id'] + '/page001.png', filename='page001.png',
        s3_uri='s3://artifacts/page001.png', size_bytes=len(output.getvalue()), content_type='image/png')
    payload['artifacts'].append(reference)
    bodies[reference['artifact_id']] = output.getvalue()
    rehash(payload)
    return payload, bodies, response, reference


def test_raster_input_does_not_consume_document_count_or_decode_as_text(tmp_path):
    payload, bodies, response, _ = image_fixture()
    with SQLiteProcessingRepository(tmp_path / 'processing.sqlite3') as store:
        model = Model(response)
        pipeline = FilingPipeline(store, Documents(bodies), model, Publisher(),
            ExtractionConfig('images-test', max_documents=3))
        assert pipeline.process(payload).outcome == 'validated'
        assert len(model.requests) == 1 and len(model.requests[0].documents) == 4


def test_image_evidence_remains_review_required(tmp_path):
    payload, bodies, response, ref = image_fixture()
    for fact in response['facts']:
        fact['source_artifact_id'] = ref['artifact_id']
    with SQLiteProcessingRepository(tmp_path / 'processing.sqlite3') as store:
        result = FilingPipeline(store, Documents(bodies), Model(response), Publisher(),
            ExtractionConfig('image-evidence-test')).process(payload)
        assert result.outcome == 'review_required'
        assert any(item['code'] == 'image_evidence_requires_review' for item in result.findings)


def test_corrupt_image_is_refused_before_model_call(tmp_path):
    payload, bodies, response, ref = image_fixture()
    bodies[ref['artifact_id']] = b'corrupt'
    ref['size_bytes'] = len(b'corrupt')
    rehash(payload)
    with SQLiteProcessingRepository(tmp_path / 'processing.sqlite3') as store:
        model = Model(response)
        result = FilingPipeline(store, Documents(bodies), model, Publisher(), ExtractionConfig('bad-image')).process(payload)
        assert result.outcome == 'review_required' and not model.requests
        assert result.findings == ({'code': 'invalid_or_oversized_supporting_image'},)


def test_nova_receives_original_image_bytes_and_labeled_artifact_identity():
    payload, bodies, response, ref = image_fixture()
    filing = FilingReady.parse(payload)
    request = ModelRequest(filing, tuple(Document(artifact, bodies[artifact.artifact_id]) for artifact in filing.artifacts),
        ExtractionConfig('images-v1', model_id=NOVA_LITE_MODEL_ID, prompt_version=NOVA_PROMPT_VERSION))
    client, seen = boto3.client('bedrock-runtime'), []
    client.meta.events.register('before-parameter-build.bedrock-runtime.Converse', lambda params, **kwargs: seen.append(params))
    result = dict(output={'message': {'role': 'assistant', 'content': [{'toolUse': {
        'toolUseId': 'extract', 'name': 'report_earnings', 'input': response}}]}}, stopReason='tool_use',
        usage={'inputTokens': 100, 'outputTokens': 50, 'totalTokens': 150}, metrics={'latencyMs': 1})
    with Stubber(client) as stub:
        stub.add_response('converse', result, {'modelId': NOVA_LITE_MODEL_ID, 'system': ANY,
            'messages': ANY, 'inferenceConfig': ANY, 'toolConfig': ANY})
        NovaLiteModel(client).classify_and_extract(request)
        stub.assert_no_pending_responses()
    blocks = seen[0]['messages'][0]['content']
    image_index = next(i for i, block in enumerate(blocks) if 'image' in block)
    assert blocks[image_index] == {'image': {'format': 'png', 'source': {'bytes': bodies[ref['artifact_id']]}}}
    assert ref['artifact_id'] in blocks[image_index - 1]['text']
    assert len([block for block in blocks if 'document' in block]) == 3
    with pytest.raises(InputReview, match='prompt_v2'):
        NovaLiteModel(client).classify_and_extract(replace(request,
            config=replace(request.config, prompt_version='eps-nova-tool-v1')))


def test_provider_image_count_bound_never_truncates_or_calls_model():
    payload, bodies, _, ref = image_fixture()
    filing = FilingReady.parse(payload)
    source = tuple(Document(a, bodies[a.artifact_id]) for a in filing.artifacts)
    image = next(doc for doc in source if doc.reference.filename.endswith('.png'))
    request = ModelRequest(filing, tuple(doc for doc in source if doc is not image) + (image,) * 21,
        ExtractionConfig('too-many-images', model_id=NOVA_LITE_MODEL_ID, prompt_version=NOVA_PROMPT_VERSION))
    with pytest.raises(InputReview, match='too_many_supporting_images'):
        NovaLiteModel(boto3.client('bedrock-runtime')).classify_and_extract(request)
