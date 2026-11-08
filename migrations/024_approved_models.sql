CREATE TABLE approved_models (
    provider text NOT NULL,
    model_id text NOT NULL,
    operation text NOT NULL CHECK (operation IN ('chat','images.generate','video','audio.speech')),
    title text NOT NULL,
    PRIMARY KEY (provider,model_id,operation)
);
INSERT INTO approved_models(provider,model_id,operation,title) VALUES
 ('anymodel','anymedia/fibo-2','images.generate','FIBO 2'),
 ('anymodel','xai/grok-imagine-video-1.5','video','Grok Imagine Video 1.5'),
 ('anymodel','fish-farm/s2.1-pro-free','audio.speech','Fish Audio S2.1 Pro Free'),
 ('anymodel','ds/deepseek-v4-flash-vision','chat','DeepSeek V4 Flash Vision'),
 ('clodex','flux-schnell','images.generate','FLUX Schnell'),
 ('clodex','gpt-image-2.5-sunburst','images.generate','Sunburst'),
 ('clodex','clodex-video/veo-3.1','video','Veo 3.1'),
 ('clodex','clodex-video/veo-3.1-fast','video','Veo 3.1 Fast'),
 ('clodex','eleven_v4','audio.speech','ElevenLabs v4');

CREATE TABLE task_markup_modes (
    provider text NOT NULL,
    model_id text NOT NULL,
    mode text NOT NULL CHECK (mode IN ('general','manual')),
    PRIMARY KEY(provider,model_id)
);
INSERT INTO task_markup_modes(provider,model_id,mode)
SELECT provider,model_id,'manual' FROM task_price_rules WHERE model_id<>'';
