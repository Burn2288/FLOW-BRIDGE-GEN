from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from elevenbot.core import Rejected
from elevenbot.interaction import MOCK_IMAGE
from elevenbot.library import LibraryItem, project_history
from types import SimpleNamespace


@pytest.mark.parametrize('kind', ['audio', 'image', 'video', 'chat'])
def test_projection_saved_or_pending(kind):
    row = {'id': uuid4(), 'kind': kind, 'model_id': 'mock', 'status': 'succeeded',
           'file_available': True, 'created_at': datetime.now(timezone.utc), 'price': None}
    projected = project_history(row)
    assert projected['id'] == row['id']
    assert projected['result_url'] == f"/api/v1/works/{kind}/{row['id']}"
    assert LibraryItem.from_history(projected).as_dict()['result_url'] == projected['result_url']
    row.update(status='uncertain', file_available=False)
    assert project_history(row)['result_url'] is None


async def test_history_projects_owned_active_and_saved_jobs(env):
    pool, _, service, owner = env
    other = await service.identity(101)
    await service.accept(other)
    image = await service.save_image_work(owner, 73311, 'fixture-image', 'fixture',
                                          SimpleNamespace(image=MOCK_IMAGE, filename='test.png'))
    owned_video, other_video = uuid4(), uuid4()
    await pool.execute("""INSERT INTO video_jobs(id,user_id,model_id,prompt,cost_usd,status)
                          VALUES($1,$2,'fixture-video','fixture',0,'polling'),
                                ($3,$4,'foreign-video','fixture',0,'polling')""",
                       owned_video, owner, other_video, other)
    quote_ids = [uuid4(), uuid4()]
    for job_id, operation in zip(quote_ids, ('chat', 'audio.speech')):
        await pool.execute("""INSERT INTO task_price_quotes(id,user_id,provider,model_id,operation,request,price,state,accepted_at)
                              VALUES($1,$2,'fixture','fixture-model',$3,'{}','{}','accepted',now())""", job_id, owner, operation)
        await pool.execute("INSERT INTO task_dispatch(quote_id,state) VALUES($1,'pending')", job_id)
    rows = await service.history(owner, include_pending_tasks=True)
    by_id = {row['id']: row for row in rows}
    assert by_id[image]['result_url'] == f'/api/v1/works/image/{image}'
    assert (by_id[owned_video]['kind'], by_id[owned_video]['status'], by_id[owned_video]['result_url']) == ('video', 'dispatching', None)
    assert (by_id[quote_ids[0]]['kind'], by_id[quote_ids[0]]['status']) == ('chat', 'queued')
    assert (by_id[quote_ids[1]]['kind'], by_id[quote_ids[1]]['status']) == ('audio', 'queued')
    assert other_video not in by_id
    telegram_rows = {row['id']: row for row in await service.history(owner)}
    assert quote_ids[0] not in telegram_rows and quote_ids[1] not in telegram_rows
    with pytest.raises(Rejected):
        await service.image_work(other, image)
