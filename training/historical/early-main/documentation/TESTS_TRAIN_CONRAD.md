### run these in order
TEST_MODE=sanity_reward python train_conrad.py
TEST_MODE=eval_base python train_conrad.py
TEST_MODE=train python train_conrad.py
TEST_MODE=eval_lora LORA_PATH=grpo_mvp_lora python train_conrad.py
TEST_MODE=eval_lora_holdout LORA_PATH=grpo_mvp_lora python train_conrad.py
